"""Sete faixas, treze passos: resultados declarados e valores privados."""

import uuid
import pytest
from django.urls import reverse
from apps.gamificacao.jornada import passos, salvar, situacao, centavos
from apps.gamificacao.models import (
    JornadaPessoal,
    RecebimentoDeclarado,
    RegistroDaJornada,
    PerfilJogador,
)

pytestmark = pytest.mark.django_db
SITE, P = "site-de-teste", "pes-abc"


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: P)


def imagem():
    from io import BytesIO
    from PIL import Image, ImageDraw
    from django.core.files.uploadedfile import SimpleUploadedFile

    b = BytesIO()
    im = Image.new("RGB", (340, 40), "white")
    ImageDraw.Draw(im).text((1, 1), "TESTE " + str(uuid.uuid4()), fill="black")
    im.save(b, format="PNG")
    return SimpleUploadedFile("teste.png", b.getvalue(), content_type="image/png")


def confirmar(r):
    from unittest.mock import patch
    from apps.gamificacao.prints_recebimentos import processar

    leitura = {
        "status": "recebido",
        "valor_cents": r.valor_original_cents,
        "moeda": r.moeda_original,
        "data": r.recebido_em.isoformat(),
    }
    with patch("apps.gamificacao.prints_recebimentos.ler_modelo", return_value=leitura):
        return processar(r.pk)


def gesto(acao, **dados):
    arquivo = (
        imagem()
        if acao in ("recebimento", "correcao") and str(dados.get("valor")) != "0"
        else None
    )
    antes, depois, avancou = salvar(
        P,
        SITE,
        {"acao": acao, "revisao": situacao(P, SITE)["revisao"], **dados},
        arquivo=arquivo,
    )
    if acao in ("recebimento", "correcao") and arquivo:
        r = RecebimentoDeclarado.objects.filter(pessoa_id=P, site_id=SITE).latest(
            "atualizado_em"
        )
        confirmar(r)
        depois = situacao(P, SITE)
        avancou = depois["atual"]["ordem"] > antes["atual"]["ordem"]
    return antes, depois, avancou


def receber(valor, **extras):
    dados = dict(
        chave=str(uuid.uuid4()), valor=valor, origem="fora", recebido_em="2026-10-01"
    )
    dados.update(extras)
    return gesto("recebimento", **dados)


@pytest.mark.parametrize("meta", [10000, 50000, 100000, 13749])
def test_sete_cores_treze_passos_preta_setimo_grau_na_meta(meta):
    lista = passos(meta)
    assert len(lista) == 13
    assert len({p["faixa"] for p in lista}) == 7
    assert [
        sum(p["faixa"] == cor for p in lista)
        for cor in ["Branca", "Amarela", "Azul", "Vermelha", "Verde", "Marrom", "Preta"]
    ] == [1, 1, 1, 1, 1, 1, 7]
    limites = [p["meta_cents"] for p in lista[5:]]
    assert limites == sorted(set(limites)) and limites[-1] == meta
    if meta == 13749:
        assert limites[0] == 172


@pytest.mark.parametrize(
    "valor,esperado", [("100,00", 10000), ("1.000,00", 100000), ("137.49", 13749)]
)
def test_centavos_sem_float(valor, esperado):
    assert centavos(valor) == esperado


@pytest.mark.parametrize(
    "valor", ["nan", "1e3", "-100", "100.0001", "", "9999999999999999999"]
)
def test_valores_invalidos(valor):
    with pytest.raises(ValueError):
        centavos(valor)


def test_sugestao_nao_fabrica_escolha(client):
    html = client.get(reverse("base")).content.decode()
    assert "7 faixas, 13 passos" in html and html.count('class="grupo-faixa"') == 7
    assert "Faixa Branca" in html and "1º Grau" in html and "sugestão" in html
    assert JornadaPessoal.objects.count() == 0


def test_preview_nao_grava_e_preserva_entrada(client):
    r = client.post(
        reverse("salvar-jornada"),
        {
            "acao": "preview-meta",
            "revisao": 0,
            "meta": "100",
            "preset": "500",
            "proposito": "Minha despesa",
        },
    )
    assert r.status_code == 200
    assert "R$ 500,00" in r.content.decode() and "R$ 6,25" in r.content.decode()
    assert "Escolher esta meta" in r.content.decode()
    assert JornadaPessoal.objects.count() == 0


def test_meta_customizada_e_recebimento_avancam_sem_xp(client):
    gesto("meta", meta="137.49", proposito="Pagar uma conta")
    _, depois, avancou = receber("137.49")
    assert (
        avancou
        and depois["atual"]["faixa"] == "Preta"
        and depois["atual"]["ordem"] == 13
    )
    assert depois["total_cents"] == 13749
    perfil = PerfilJogador.objects.get(pessoa_id=P)
    assert perfil.xp_total == 0 and perfil.cristais_saldo == 0
    assert "Pagar uma conta" in client.get(reverse("base")).content.decode()


def test_iniciar_sandbox_nao_concede_grau():
    from apps.gamificacao.faixas import registrar_fato
    from django.utils import timezone

    registrar_fato(
        P,
        SITE,
        "sandbox",
        event_id="sandbox-iniciado",
        quando=timezone.now(),
        historico=False,
    )
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    gesto("declaracao", passo="3", estado="feito")
    assert situacao(P, SITE)["atual"]["ordem"] == 3


def test_reenvio_nao_duplica_recebimento():
    gesto("meta", meta="500")
    dados = {
        "acao": "recebimento",
        "revisao": 1,
        "chave": str(uuid.uuid4()),
        "valor": "30",
        "origem": "fora",
        "recebido_em": "2026-10-01",
    }
    salvar(P, SITE, dados, arquivo=imagem())
    confirmar(RecebimentoDeclarado.objects.get())
    salvar(P, SITE, dados)
    assert (
        situacao(P, SITE)["total_cents"] == 3000
        and RecebimentoDeclarado.objects.count() == 1
    )


@pytest.mark.django_db(transaction=True)
def test_recebimento_simultaneo_com_mesma_chave_so_soma_uma_vez():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections

    gesto("meta", meta="500")
    dados = {
        "acao": "recebimento",
        "revisao": 1,
        "chave": str(uuid.uuid4()),
        "valor": "30",
        "origem": "fora",
        "recebido_em": "2026-10-01",
    }
    barreira = Barrier(2)

    def enviar():
        close_old_connections()
        try:
            barreira.wait(timeout=10)
            return salvar(P, SITE, dados, arquivo=imagem())
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda _: enviar(), range(2)))
    assert len(resultados) == 2
    confirmar(RecebimentoDeclarado.objects.get())
    assert (
        situacao(P, SITE)["total_cents"] == 3000
        and RecebimentoDeclarado.objects.count() == 1
    )


def test_correcao_guarda_historia_sem_apagar():
    gesto("meta", meta="100")
    receber("100")
    r = RecebimentoDeclarado.objects.get()
    gesto("correcao", recebimento=r.pk, valor="20", recebido_em="2026-10-01")
    assert (
        situacao(P, SITE)["total_cents"] == 2000
        and situacao(P, SITE)["atual"]["ordem"] == 9
    )
    assert (
        RegistroDaJornada.objects.filter(acao="correcao").get().dados["passo_antes"]
        == 13
    )
    gesto("correcao", recebimento=r.pk, valor="0", recebido_em="2026-10-01")
    assert (
        situacao(P, SITE)["total_cents"] == 0
        and RecebimentoDeclarado.objects.count() == 1
    )


def test_troca_meta_preserva_recebimentos_e_historico():
    gesto("meta", meta="100")
    receber("100")
    gesto("meta", meta="1000")
    s = situacao(P, SITE)
    assert s["total_cents"] == 10000 and s["atual"]["ordem"] == 9
    assert (
        RegistroDaJornada.objects.filter(acao="meta").first().dados["passo_antes"] == 13
    )


def test_fila_um_recebimento_corrigivel_e_proxima_acao_forum():
    receber("10", origem="fila")
    gesto(
        "correcao",
        recebimento=RecebimentoDeclarado.objects.get().pk,
        valor="20",
        recebido_em="2026-10-01",
    )
    assert situacao(P, SITE)["total_cents"] == 2000
    assert situacao(P, SITE)["proxima_url"] == "/forum/"


def test_dois_pix_da_fila_somam_e_reenvio_nao_duplica():
    receber("10", origem="fila")
    chave = str(uuid.uuid4())
    for _ in range(2):
        receber("15", origem="fila", chave=chave)
    assert RecebimentoDeclarado.objects.count() == 2
    s = situacao(P, SITE)
    assert s["total_cents"] == 2500 and s["fila_usada"]


def test_apoio_muda_orientacao_sem_mudar_criterio():
    antes = situacao(P, SITE)["lista"]
    gesto("apoio", apoio="desafio")
    assert (
        situacao(P, SITE)["lista"] == antes
        and "outra versão" in situacao(P, SITE)["dica"]
    )


def test_nao_corrige_recebimento_alheio():
    receber("10")
    r = RecebimentoDeclarado.objects.get()
    for pessoa, site in [("outra-pessoa", SITE), (P, "outro-site")]:
        with pytest.raises(ValueError, match="não encontrado"):
            salvar(
                pessoa,
                site,
                {
                    "acao": "correcao",
                    "revisao": 0,
                    "recebimento": r.pk,
                    "valor": "999",
                    "recebido_em": "2026-10-01",
                },
                arquivo=imagem(),
            )
    assert situacao(P, SITE)["total_cents"] == 1000


def test_aba_antiga_nao_sobrescreve():
    gesto("meta", meta="500")
    with pytest.raises(ValueError, match="outra aba"):
        salvar(P, SITE, {"acao": "meta", "revisao": 0, "meta": "100"})
    assert situacao(P, SITE)["meta_cents"] == 50000


def test_api_nao_revela_meta_valor_proposito(client, monkeypatch):
    from django.conf import settings

    monkeypatch.setattr(settings, "TOKENS_ACEITOS", ["teste-jornada"])
    gesto("meta", meta="137.49", proposito="MOTIVO-PRIVADO")
    receber("20")
    r = client.get(
        "/api/gamificacao/faixa-do-aluno",
        {"pessoa_id": P},
        HTTP_AUTHORIZATION="Bearer teste-jornada",
    )
    assert r.status_code == 200 and r.json()["atual"]["nome"] == "Preta · 3º Grau"
    for privado in ["137.49", "13749", "MOTIVO-PRIVADO", "20,00"]:
        assert privado not in r.content.decode()


def test_visitante_e_csrf_nao_gravam(client, monkeypatch):
    from django.test import Client

    assert (
        Client(enforce_csrf_checks=True)
        .post(reverse("salvar-jornada"), {"acao": "meta", "meta": "100", "revisao": 0})
        .status_code
        == 403
    )
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)
    assert (
        client.post(
            reverse("salvar-jornada"), {"acao": "meta", "meta": "100", "revisao": 0}
        ).status_code
        == 302
    )
    assert JornadaPessoal.objects.count() == 0


def test_texto_e_escapado(client):
    gesto("meta", meta="100", proposito='<script>alert("x")</script>')
    html = client.get(reverse("base")).content.decode()
    assert '<script>alert("x")</script>' not in html and "&lt;script&gt;" in html


def _corrigir_sem_confirmar(r, valor):
    salvar(
        P,
        SITE,
        {
            "acao": "correcao",
            "revisao": situacao(P, SITE)["revisao"],
            "recebimento": r.pk,
            "valor": valor,
            "recebido_em": "2026-10-01",
        },
        arquivo=imagem(),
    )
    r.refresh_from_db()
    return r


def test_correcao_pendente_mantem_total_e_passo():
    gesto("meta", meta="100")
    receber("100")
    r = RecebimentoDeclarado.objects.get()
    _corrigir_sem_confirmar(r, "100")
    s = situacao(P, SITE)
    assert r.estado == "pendente" and s["total_cents"] == 10000
    assert s["atual"]["ordem"] == 13
    reg = RegistroDaJornada.objects.filter(acao="correcao").get()
    assert reg.dados["passo_depois"] == 13


def test_reconfirmar_correcao_igual_nao_comemora():
    gesto("meta", meta="100")
    receber("100")
    j = JornadaPessoal.objects.get()
    j.celebracao_pendente = {}
    j.save()
    r = RecebimentoDeclarado.objects.get()
    _corrigir_sem_confirmar(r, "100")
    confirmar(r)
    j.refresh_from_db()
    assert j.celebracao_pendente == {}


def test_correcao_maior_comemora_so_passo_novo():
    gesto("meta", meta="100")
    receber("30")
    j = JornadaPessoal.objects.get()
    j.celebracao_pendente = {}
    j.save()
    r = RecebimentoDeclarado.objects.get()
    antes = situacao(P, SITE)["atual"]["ordem"]
    _corrigir_sem_confirmar(r, "100")
    assert situacao(P, SITE)["atual"]["ordem"] == antes
    confirmar(r)
    j.refresh_from_db()
    assert j.celebracao_pendente["ordem"] == situacao(P, SITE)["atual"]["ordem"] > antes


def test_correcao_que_vira_esclarecer_deixa_de_somar():
    from unittest.mock import patch
    from apps.gamificacao.prints_recebimentos import processar

    receber("50")
    r = RecebimentoDeclarado.objects.get()
    _corrigir_sem_confirmar(r, "60")
    assert situacao(P, SITE)["total_cents"] == 5000
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo",
        return_value={"status": "ilegivel"},
    ):
        processar(r.pk)
    r.refresh_from_db()
    assert r.estado == "esclarecer" and situacao(P, SITE)["total_cents"] == 0


def test_anular_confirmado_zera_na_hora():
    receber("50")
    r = RecebimentoDeclarado.objects.get()
    gesto("correcao", recebimento=r.pk, valor="0", recebido_em="2026-10-01")
    r.refresh_from_db()
    assert r.estado == "anulado" and r.leitura == {}
    assert situacao(P, SITE)["total_cents"] == 0


def test_duas_correcoes_seguidas_mantem_anterior_original():
    receber("50")
    r = RecebimentoDeclarado.objects.get()
    _corrigir_sem_confirmar(r, "60")
    _corrigir_sem_confirmar(r, "70")
    assert r.leitura == {"anterior_cents": 5000}
    assert situacao(P, SITE)["total_cents"] == 5000


def test_cinco_falhas_do_leitor_em_correcao_mantem_valor_antigo():
    from unittest.mock import patch
    from apps.gamificacao.prints_recebimentos import processar

    gesto("meta", meta="100")
    receber("100")
    j = JornadaPessoal.objects.get()
    j.celebracao_pendente = {}
    j.save()
    r = RecebimentoDeclarado.objects.get()
    _corrigir_sem_confirmar(r, "100")
    RecebimentoDeclarado.objects.filter(pk=r.pk).update(tentativas=4)
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo",
        side_effect=RuntimeError("fora"),
    ):
        processar(r.pk)
    r.refresh_from_db()
    assert r.estado == "esclarecer" and r.leitura["motivo"] == "leitor"
    s = situacao(P, SITE)
    assert s["total_cents"] == 10000 and s["atual"]["ordem"] == 13
    assert (
        RegistroDaJornada.objects.filter(acao="leitura-print")
        .latest("id")
        .dados["passo_depois"]
        == 13
    )
    confirmar(r)
    j.refresh_from_db()
    assert j.celebracao_pendente == {}


def test_correcao_sobre_esclarecer_do_leitor_mantem_total_e_nao_comemora():
    from unittest.mock import patch
    from apps.gamificacao.prints_recebimentos import processar

    gesto("meta", meta="100")
    receber("100")
    j = JornadaPessoal.objects.get()
    j.celebracao_pendente = {}
    j.save()
    r = RecebimentoDeclarado.objects.get()
    _corrigir_sem_confirmar(r, "100")
    RecebimentoDeclarado.objects.filter(pk=r.pk).update(tentativas=4)
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo",
        side_effect=RuntimeError("fora"),
    ):
        processar(r.pk)
    r.refresh_from_db()
    assert r.estado == "esclarecer" and r.leitura["motivo"] == "leitor"
    _corrigir_sem_confirmar(r, "100")
    r.refresh_from_db()
    assert r.leitura == {"anterior_cents": 10000}
    s = situacao(P, SITE)
    assert s["total_cents"] == 10000 and s["atual"]["ordem"] == 13
    assert (
        RegistroDaJornada.objects.filter(acao="correcao").latest("id").dados["passo_depois"]
        == 13
    )
    confirmar(r)
    j.refresh_from_db()
    assert j.celebracao_pendente == {}


def _rejeitar_correcao(r, valor):
    from unittest.mock import patch
    from apps.gamificacao.prints_recebimentos import processar

    _corrigir_sem_confirmar(r, valor)
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo",
        return_value={"status": "ilegivel"},
    ):
        processar(r.pk)
    r.refresh_from_db()
    assert r.estado == "esclarecer" and r.leitura["motivo"] == "status"


def _limpar_celebracao():
    j = JornadaPessoal.objects.get()
    j.celebracao_pendente = {}
    j.save()
    return j


def test_correcao_rejeitada_e_reconfirmada_nao_comemora_de_novo():
    gesto("meta", meta="100")
    receber("100")
    j = _limpar_celebracao()
    assert j.declaracoes["maior_passo_comemorado"] == 13
    r = RecebimentoDeclarado.objects.get()
    _rejeitar_correcao(r, "100")
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    _corrigir_sem_confirmar(r, "100")
    confirmar(r)
    assert situacao(P, SITE)["atual"]["ordem"] == 13
    j.refresh_from_db()
    assert j.celebracao_pendente == {}
    assert j.declaracoes["maior_passo_comemorado"] == 13


def test_passo_realmente_novo_depois_da_queda_ainda_comemora():
    gesto("meta", meta="1000")
    receber("300")
    j = _limpar_celebracao()
    maior = j.declaracoes["maior_passo_comemorado"]
    r = RecebimentoDeclarado.objects.get()
    _rejeitar_correcao(r, "300")
    _corrigir_sem_confirmar(r, "300")
    confirmar(r)
    j.refresh_from_db()
    assert j.celebracao_pendente == {}
    receber("600")
    j.refresh_from_db()
    novo = situacao(P, SITE)["atual"]["ordem"]
    assert novo > maior
    assert j.celebracao_pendente["ordem"] == novo
    assert j.declaracoes["maior_passo_comemorado"] == novo


def test_jornada_antiga_sem_o_campo_usa_o_historico_de_comemoracoes():
    gesto("meta", meta="100")
    receber("100")
    j = _limpar_celebracao()
    j.declaracoes = {
        k: v for k, v in j.declaracoes.items() if k != "maior_passo_comemorado"
    }
    j.save()
    r = RecebimentoDeclarado.objects.get()
    _rejeitar_correcao(r, "100")
    _corrigir_sem_confirmar(r, "100")
    confirmar(r)
    j.refresh_from_db()
    assert j.celebracao_pendente == {}
