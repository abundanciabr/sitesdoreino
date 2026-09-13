"""A versão conferida é a servida, e uma cópia alternativa não fica oculta."""

import hashlib
import json
import os

import pytest
from django.test import RequestFactory

from apps.core import admin_dados, direcao, painel, placar


def pacote(
    pasta, *, sha="a" * 40, run=10, texto="VERSAO-A", tipo="painel", extras=None
):
    pasta.mkdir()
    (pasta / "registros").mkdir()
    (pasta / "cartoes").mkdir()
    (pasta / "registros" / "registro.js").write_text("{}", encoding="utf-8")
    (pasta / "cartoes" / "cartao.json").write_text("{}", encoding="utf-8")
    (pasta / "livro-202609.js").write_text("window.LIVRO = [];", encoding="utf-8")
    (pasta / "painel.html").write_text(
        f"<!doctype html><html><body>{texto}</body></html>", encoding="utf-8"
    )
    for nome, conteudo in (extras or {}).items():
        (pasta / nome).write_text(json.dumps(conteudo), encoding="utf-8")
    manifesto = {
        "formato": "admin-dados.v1",
        "tipo": tipo,
        "origem": {
            "sha": sha,
            "run_id": str(run * 100),
            "run_number": run,
            "gerado_em": "2026-09-09T10:00:00+00:00",
        },
        "integridade": {
            "algoritmo": "sha256",
            "arquivos": {
                p.relative_to(pasta)
                .as_posix(): hashlib.sha256(p.read_bytes())
                .hexdigest()
                for p in pasta.rglob("*")
                if p.is_file()
            },
        },
    }
    (pasta / "admin-dados.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return pasta


def apontar(destino, ponteiro):
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(destino), str(ponteiro))
    else:
        ponteiro.symlink_to(destino, target_is_directory=True)


def retirar_ponteiro(ponteiro):
    if os.name == "nt":
        assert ponteiro.is_junction()
        ponteiro.rmdir()
    else:
        assert ponteiro.is_symlink()
        ponteiro.unlink()


def test_copia_antiga_identificada_na_tela_e_na_resposta(tmp_path, monkeypatch):
    atual = pacote(tmp_path / "atual")
    antiga = pacote(
        tmp_path / "painel_embutido", sha="b" * 40, run=9, texto="COPIA-ANTIGA"
    )
    (atual / "painel.html").write_text("CORROMPIDO", encoding="utf-8")
    monkeypatch.setattr(painel, "CANDIDATOS", (atual, antiga))

    resposta = painel.painel(RequestFactory().get("/painel/"))

    assert resposta.status_code == 200
    assert b"COPIA-ANTIGA" in resposta.content
    assert "cópia alternativa" in resposta.content.decode()
    assert "integridade" in resposta.content.decode()
    assert resposta["X-Admin-Dados-Sha"] == "b" * 40
    assert resposta["X-Admin-Dados-Run"] == "900"
    assert resposta["X-Admin-Dados-Condicao"] == "alternativa"
    assert str(tmp_path) not in str(dict(resposta.headers))
    assert str(tmp_path) not in resposta.content.decode()


def test_troca_do_ponteiro_nao_muda_a_versao_ja_conferida(tmp_path, monkeypatch):
    primeira = pacote(tmp_path / "release-a")
    segunda = pacote(tmp_path / "release-b", sha="b" * 40, run=11, texto="VERSAO-B")
    ponteiro = tmp_path / "painel_ativo"
    apontar(primeira, ponteiro)
    monkeypatch.setattr(painel, "CANDIDATOS", (ponteiro,))
    sha_original = admin_dados._sha256
    trocou = False

    def hash_e_troca(caminho):
        nonlocal trocou
        resultado = sha_original(caminho)
        if caminho.name == "painel.html" and not trocou:
            retirar_ponteiro(ponteiro)
            apontar(segunda, ponteiro)
            trocou = True
        return resultado

    monkeypatch.setattr(admin_dados, "_sha256", hash_e_troca)
    try:
        resposta = painel.painel(RequestFactory().get("/painel/"))
        assert trocou
        assert b"VERSAO-A" in resposta.content
        assert b"VERSAO-B" not in resposta.content
        assert resposta["X-Admin-Dados-Sha"] == "a" * 40
    finally:
        retirar_ponteiro(ponteiro)


@pytest.mark.parametrize(
    "modulo,leitor,subpasta",
    [
        (direcao, "diretorio_dos_registros", "registros"),
        (placar, "diretorio_dos_cartoes", "cartoes"),
    ],
)
def test_indicadores_usam_a_mesma_copia_validada(
    tmp_path, monkeypatch, modulo, leitor, subpasta
):
    atual = pacote(tmp_path / "atual")
    antiga = pacote(tmp_path / "painel_embutido", sha="b" * 40, run=9)
    (atual / "registros" / "registro.js").write_text("ADULTERADO", encoding="utf-8")
    candidatos = (atual, antiga)
    monkeypatch.setattr(painel, "CANDIDATOS", candidatos)
    monkeypatch.setattr(modulo, "CANDIDATOS", candidatos, raising=False)

    assert getattr(modulo, leitor)() == antiga.resolve() / subpasta


def test_pacote_com_manifesto_sem_origem_e_recusado(tmp_path):
    pasta = pacote(tmp_path / "publicacao")
    arquivo = pasta / "admin-dados.json"
    manifesto = json.loads(arquivo.read_text())
    del manifesto["origem"]
    arquivo.write_text(json.dumps(manifesto), encoding="utf-8")

    assert admin_dados.selecionar_dados((pasta,), tipo="painel") is None


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("sha", ""),
        ("sha", "a" * 39),
        ("run_id", ""),
        ("run_id", "1\r\nOutro: valor"),
        ("run_number", True),
        ("run_number", 0),
        ("gerado_em", "2026-09-09T10:00:00"),
        ("gerado_em", "não é uma data"),
    ],
)
def test_identificacao_invalida_nao_pode_ser_publicacao(tmp_path, campo, valor):
    pasta = pacote(tmp_path / "publicacao")
    arquivo = pasta / "admin-dados.json"
    manifesto = json.loads(arquivo.read_text())
    manifesto["origem"][campo] = valor
    arquivo.write_text(json.dumps(manifesto), encoding="utf-8")
    assert admin_dados.selecionar_dados((pasta,), tipo="painel") is None


def test_manifesto_que_nao_e_objeto_nao_derruba_a_selecao(tmp_path):
    pasta = pacote(tmp_path / "publicacao")
    (pasta / "admin-dados.json").write_text("[]", encoding="utf-8")
    assert admin_dados.selecionar_dados((pasta,), tipo="painel") is None


def test_legado_local_continua_disponivel_com_identidade_desconhecida(
    tmp_path, monkeypatch
):
    pasta = pacote(tmp_path / "painel_embutido")
    (pasta / "admin-dados.json").unlink()
    monkeypatch.setattr(painel, "CANDIDATOS", (pasta,))
    dados = admin_dados.selecionar_dados((pasta,), tipo="painel")
    assert dados.pasta == pasta.resolve()
    assert dados.sha is None
    assert dados.condicao == "legado"
    assert dados.origem == "embutido"
    resposta = painel.painel(RequestFactory().get("/painel/"))
    assert "Cópia legada" in resposta.content.decode()
    assert resposta["X-Admin-Dados-Sha"] == "desconhecida"


def test_publicacao_sem_manifesto_nao_pode_passar_como_legado(tmp_path, monkeypatch):
    raiz = tmp_path / "publicados"
    raiz.mkdir()
    pasta = pacote(raiz / "painel_ativo")
    (pasta / "admin-dados.json").unlink()
    monkeypatch.setattr(admin_dados, "PASTA_DADOS_ADMIN", raiz)
    assert admin_dados.selecionar_dados((pasta,), tipo="painel") is None


def test_arquivo_mensal_identifica_a_versao_servida(tmp_path, monkeypatch):
    pasta = pacote(tmp_path / "publicacao")
    monkeypatch.setattr(painel, "CANDIDATOS", (pasta,))
    resposta = painel.painel_arquivo(
        RequestFactory().get("/painel/livro-202609.js"), "livro-202609.js"
    )
    try:
        assert resposta.status_code == 200
        assert resposta["X-Admin-Dados-Sha"] == "a" * 40
        assert resposta["X-Admin-Dados-Run"] == "1000"
        assert resposta["X-Admin-Dados-Condicao"] == "verificada"
        assert resposta["Cache-Control"] == "no-store"
        assert (
            b"".join(resposta.streaming_content)
            == (pasta / "livro-202609.js").read_bytes()
        )
    finally:
        resposta.close()


def test_sem_copia_valida_a_pagina_explica_a_falha(tmp_path, monkeypatch):
    pasta = pacote(tmp_path / "publicacao")
    (pasta / "painel.html").write_text("CORROMPIDO", encoding="utf-8")
    monkeypatch.setattr(painel, "CANDIDATOS", (pasta,))
    resposta = painel.painel(RequestFactory().get("/painel/"))
    assert resposta.status_code == 500
    assert (
        "Nenhuma cópia disponível passou pela conferência" in resposta.content.decode()
    )
    assert resposta["X-Admin-Dados-Condicao"] == "indisponivel"
    assert resposta["Cache-Control"] == "no-store"


def test_resposta_composta_fixa_a_versao_e_a_proxima_requisicao_ve_a_nova(
    tmp_path, monkeypatch
):
    from django.http import HttpResponse
    from apps.core.porta import PortaAdministrativa

    primeira = pacote(tmp_path / "release-a")
    segunda = pacote(tmp_path / "release-b", sha="b" * 40)
    ponteiro = tmp_path / "painel_ativo"
    apontar(primeira, ponteiro)
    monkeypatch.setattr(painel, "CANDIDATOS", (ponteiro,))
    chamadas = []

    def montar(request):
        cartoes = placar.diretorio_dos_cartoes()
        if not chamadas:
            retirar_ponteiro(ponteiro)
            apontar(segunda, ponteiro)
        registros = direcao.diretorio_dos_registros()
        chamadas.append((cartoes.parent, registros.parent))
        return HttpResponse("ok")

    porta = PortaAdministrativa(montar)
    try:
        porta(RequestFactory().get("/healthz"))
        porta(RequestFactory().get("/healthz"))
        assert chamadas == [(primeira, primeira), (segunda, segunda)]
    finally:
        retirar_ponteiro(ponteiro)


def test_requisicoes_concorrentes_nao_compartilham_selecao(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from django.http import HttpResponse
    from apps.core.porta import PortaAdministrativa

    primeira = pacote(tmp_path / "release-a")
    segunda = pacote(tmp_path / "release-b", sha="b" * 40)
    ponteiro = tmp_path / "painel_ativo"
    apontar(primeira, ponteiro)
    monkeypatch.setattr(painel, "CANDIDATOS", (ponteiro,))
    selecionou = Event()
    terminou_segunda = Event()

    def montar(request):
        inicio = painel.diretorio_do_painel()
        if request.GET.get("primeira"):
            selecionou.set()
            assert terminou_segunda.wait(10)
        else:
            terminou_segunda.set()
        fim = direcao.diretorio_dos_registros().parent
        return HttpResponse(f"{inicio.name}/{fim.name}")

    porta = PortaAdministrativa(montar)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            resposta_a = pool.submit(porta, RequestFactory().get("/healthz?primeira=1"))
            assert selecionou.wait(10)
            retirar_ponteiro(ponteiro)
            apontar(segunda, ponteiro)
            resposta_b = pool.submit(porta, RequestFactory().get("/healthz"))
            assert resposta_b.result(timeout=10).content == b"release-b/release-b"
            assert resposta_a.result(timeout=10).content == b"release-a/release-a"
    finally:
        terminou_segunda.set()
        retirar_ponteiro(ponteiro)


@pytest.mark.parametrize("saida", ["excecao", "recusa"])
def test_porta_descarta_selecao_apos_excecao_ou_recusa(tmp_path, monkeypatch, saida):
    from django.http import HttpResponse
    from apps.core.porta import PortaAdministrativa

    primeira = pacote(tmp_path / "release-a")
    segunda = pacote(tmp_path / "release-b", sha="b" * 40)
    monkeypatch.setattr(painel, "CANDIDATOS", (primeira,))

    def interromper(request):
        assert painel.diretorio_do_painel() == primeira
        if saida == "excecao":
            raise ValueError("interrompida")
        return HttpResponse(status=302)

    porta = PortaAdministrativa(interromper)
    if saida == "recusa":
        monkeypatch.setattr(porta, "_para_o_login", interromper)
        assert porta(RequestFactory().get("/painel/")).status_code == 302
    else:
        with pytest.raises(ValueError, match="interrompida"):
            porta(RequestFactory().get("/healthz"))
    monkeypatch.setattr(painel, "CANDIDATOS", (segunda,))
    assert painel.diretorio_do_painel() == segunda


def test_artefato_ausente_na_versao_fixada_nao_troca_de_pacote(tmp_path):
    from django.http import HttpResponse
    from apps.core.porta import PortaAdministrativa

    primeira = pacote(tmp_path / "release-a")
    segunda = pacote(
        tmp_path / "release-b", sha="a" * 40, extras={"livro-ausente.js": {}}
    )

    def montar(request):
        selecionado = admin_dados.selecionar_dados((primeira,), tipo="painel")
        assert selecionado.pasta == primeira
        assert (
            admin_dados.selecionar_dados(
                (segunda,), tipo="painel", arquivos_obrigatorios=("livro-ausente.js",)
            )
            is None
        )
        assert admin_dados.selecionar_dados((segunda,), tipo="painel") == selecionado
        return HttpResponse("ok")

    PortaAdministrativa(montar)(RequestFactory().get("/healthz"))


def test_indisponibilidade_fica_fixada_ate_o_fim_da_resposta(tmp_path):
    from django.http import HttpResponse
    from apps.core.porta import PortaAdministrativa

    pasta = pacote(tmp_path / "release")

    def montar(request):
        assert (
            admin_dados.selecionar_dados((tmp_path / "ausente",), tipo="painel") is None
        )
        assert admin_dados.selecionar_dados((pasta,), tipo="painel") is None
        return HttpResponse("ok")

    PortaAdministrativa(montar)(RequestFactory().get("/healthz"))
    assert admin_dados.selecionar_dados((pasta,), tipo="painel").pasta == pasta


def test_fila_json_usa_a_publicacao_atual_de_cada_tipo(tmp_path, monkeypatch):
    from apps.core import fila_do_painel, robos
    from apps.core.porta import PortaAdministrativa

    estados = {
        "TAR-001": {"estado": "na fila", "titulo": "Tarefa A", "toca": ["admin"]}
    }
    fila_a = pacote(tmp_path / "fila-a", tipo="fila", extras={"estados.json": estados})
    areas_a = {"areas": [{"id": "area-a", "celulas": ["admin"]}]}
    areas_b = {"areas": [{"id": "area-b", "celulas": ["admin"]}]}
    painel_a = pacote(tmp_path / "painel-a", extras={"areas.json": areas_a})
    painel_b = pacote(
        tmp_path / "painel-b", sha="b" * 40, extras={"areas.json": areas_b}
    )
    ponteiro = tmp_path / "painel_ativo"
    apontar(painel_a, ponteiro)
    monkeypatch.setattr(robos, "CANDIDATOS", (fila_a,))
    monkeypatch.setattr(painel, "CANDIDATOS", (ponteiro,))
    leitor = robos.diretorio_da_fila

    def ler_fila_e_trocar():
        resultado = leitor()
        retirar_ponteiro(ponteiro)
        apontar(painel_b, ponteiro)
        return resultado

    monkeypatch.setattr(robos, "diretorio_da_fila", ler_fila_e_trocar)
    try:
        resposta = PortaAdministrativa(fila_do_painel.fila_json)(
            RequestFactory().get("/healthz")
        )
        dados = json.loads(resposta.content)
        assert dados["erro"] is None
        assert dados["tarefas"][0]["titulo"] == "Tarefa A"
        assert dados["tarefas"][0]["area"] == "area-b"
        assert dados["aviso"] is None
    finally:
        retirar_ponteiro(ponteiro)


def test_artefato_de_diretorio_ausente_nao_troca_a_fila_fixada(tmp_path):
    from django.http import HttpResponse
    from apps.core.porta import PortaAdministrativa

    primeira = pacote(tmp_path / "fila-a", tipo="fila")
    segunda = pacote(tmp_path / "fila-b", tipo="fila")
    (segunda / "eventos").mkdir()

    def montar(request):
        assert admin_dados.selecionar_dados((primeira,), tipo="fila").pasta == primeira
        assert (
            admin_dados.selecionar_dados(
                (segunda,), tipo="fila", diretorios_obrigatorios=("eventos",)
            )
            is None
        )
        return HttpResponse("ok")

    PortaAdministrativa(montar)(RequestFactory().get("/healthz"))


def test_painel_e_fila_de_execucoes_distintas_ficam_disponiveis_na_mesma_resposta(
    tmp_path,
):
    from django.http import HttpResponse
    from apps.core.porta import PortaAdministrativa

    painel_a = pacote(tmp_path / "painel-a", run=10)
    fila_b = pacote(tmp_path / "fila-b", run=11, tipo="fila")

    def montar(request):
        assert (
            admin_dados.selecionar_dados((painel_a,), tipo="painel").pasta == painel_a
        )
        assert admin_dados.selecionar_dados((fila_b,), tipo="fila").pasta == fila_b
        return HttpResponse("ok")

    PortaAdministrativa(montar)(RequestFactory().get("/healthz"))
