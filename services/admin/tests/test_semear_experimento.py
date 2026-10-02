"""`manage.py semear_experimento`: o A/A técnico da oferta ligado, desligado e medido pelo pipeline.

O comando é a segunda porta das mesmas regras da tela `/admin/paginas/experimentos/`,
da decisão e do resultado do experimento, para o robô rodar o ensaio sem navegador
e sem login. O catálogo falso aqui guarda estado, nos endereços do contrato, para
que rodar duas vezes seja de fato rodar duas vezes contra o mesmo catálogo. Os
guardas:

1. **Criar e iniciar com a assinatura certa**: hipótese exata, `a` sem texto (o
   catálogo grava o publicado), `b` com o texto publicado, 5000/5000, taxa base
   3%, efeito mínimo 1 ponto, 7 dias, métrica da tela. Auditoria das duas
   escritas, assinada pelo semeador e sem dado pessoal.
2. **Idempotência**: rodar de novo com o A/A no ar não cria nada e diz PRONTO.
3. **Só a assinatura inteira é o A/A**: outra hipótese, outro espaço, uma
   variante só ou textos diferentes fazem parar, sem tocar no experimento.
4. **A/A em rascunho é iniciado**, sem nascer um segundo.
5. **Encerrar só encerra o A/A**, com a decisão `encerrar`, e nunca um
   experimento comum. Sem A/A no ar, sai verde sem mudar nada.
6. **A releitura morde**: o catálogo falso pode devolver, na releitura, outro
   estado, outra decisão, outra forma ou textos diferentes, e nenhum deles vira
   linha `PRONTO:`. A página publicada entre a leitura e o início deixa o
   experimento no ar com textos diferentes, e a parada diz isso e onde encerrá-lo.
7. **Um site só**: meshcraft.top, sem `--host`; o site ausente para com as duas
   causas e o que fazer em cada uma, e todo link das mensagens é rota da admin.
8. **Medir só lê**, pela conta da tela de resultado, e para sem PRONTO quando a
   medição está fora do ar ou responde fora do combinado.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from io import StringIO
from urllib.parse import urlsplit

import httpx
import pytest
import respx
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import resolve
from django.utils import timezone

from apps.auditoria.models import Registro
from apps.core.clients import MedicaoClient
from apps.core.management.commands import semear_experimento
from apps.core.paginas import SLUG_DA_PAGINA

CATALOGO = "http://catalogo:8000/api/catalogo"
FUNIL = "http://metricas:8000/api/metricas/funil"
HOST = "meshcraft.top"
SITE_ID = "site-mesh"
TITULO_NO_AR = "Modele para imprimir, do primeiro cubo à peça vendida"
HIPOTESE = "A/A técnico: mede sorteio, exposição e contagem, não conversão"
HOJE = dt.date(2026, 9, 29)
#: Os endereços do catálogo que o comando chama.
CAMINHOS = {
    "getSiteByHost": "/sites/by-host/{host}",
    "getPage": "/sites/{site_id}/paginas/{slug}",
    "listExperiments": "/sites/{site_id}/paginas/{slug}/experimentos",
    "getExperiment": "/sites/{site_id}/paginas/{slug}/experimentos/{experimento_id}",
}


def _do_contrato(operacao: str) -> str:
    """O endereço da operação, com o id como padrão."""
    return CATALOGO + CAMINHOS[operacao].format(
        host=HOST,
        site_id=SITE_ID,
        slug=SLUG_DA_PAGINA,
        experimento_id="{experimento_id}",
    )


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    monkeypatch.setenv("METRICAS_API_URL", FUNIL.removesuffix("/funil"))
    monkeypatch.setenv("METRICAS_API_TOKEN", "token-do-par-admin-metricas")
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: HOJE)


class CatalogoFalso:
    """O catálogo, com memória: cria, lista, lê e muda estado como o de verdade.

    `releitura` troca campos do experimento lido DEPOIS de uma mudança de
    estado, que é a releitura do comando. `publicar_ao_iniciar` publica um
    título novo no instante do início, como a corrida entre as duas leituras.
    """

    def __init__(self, texto_no_ar: str = TITULO_NO_AR, *, site=True):
        self.texto_no_ar = texto_no_ar
        self.experimentos: list[dict] = []
        self.criacoes = 0
        self.mudancas: list[tuple[str, dict]] = []
        self.releitura: dict = {}
        self.publicar_ao_iniciar = ""
        respx.get(_do_contrato("getSiteByHost")).mock(
            return_value=(
                httpx.Response(200, json={"id": SITE_ID, "host": HOST})
                if site
                else httpx.Response(404, json={"detail": "site inexistente"})
            )
        )
        respx.get(_do_contrato("getPage")).mock(side_effect=self._pagina)
        lista = _do_contrato("listExperiments")
        respx.get(lista).mock(side_effect=self._listar)
        respx.post(lista).mock(side_effect=self._criar)
        um = _do_contrato("getExperiment").replace("{experimento_id}", "")
        respx.get(url__regex=rf"^{um}[0-9a-f-]+$").mock(side_effect=self._ler)
        respx.post(url__regex=rf"^{um}[0-9a-f-]+/estado$").mock(side_effect=self._mudar)

    def experimento(
        self,
        estado,
        *,
        hipotese=HIPOTESE,
        texto_b=None,
        texto_a=None,
        slot="headline",
        variantes=2,
    ):
        corpo = {
            "id": str(uuid.uuid4()),
            "site_id": SITE_ID,
            "slug": SLUG_DA_PAGINA,
            "secao": "cubo",
            "slot": slot,
            "hipotese": hipotese,
            "metrica_principal": "cta_checkout",
            "taxa_base": 0.03,
            "mde": 0.01,
            "n_por_braco_planejado": 5000,
            "dias_planejados": 7,
            "estado": estado,
            "decisao": None,
            "vencedora": None,
            "criado_em": "2026-09-27T10:00:00Z",
            "iniciado_em": "2026-09-27T11:00:00Z" if estado == "ativo" else None,
            "fim_planejado": None,
            "encerrado_em": None,
            "variantes": [
                {
                    "variante_id": "a",
                    "peso": 5000,
                    "valor": texto_a or self.texto_no_ar,
                },
                {
                    "variante_id": "b",
                    "peso": 5000,
                    "valor": texto_b or self.texto_no_ar,
                },
            ][:variantes],
        }
        self.experimentos.insert(0, corpo)
        return corpo

    def _pagina(self, request):
        return httpx.Response(
            200,
            json={
                "id": "versao-3",
                "site_id": SITE_ID,
                "slug": SLUG_DA_PAGINA,
                "version": 3,
                "published_at": "2026-09-20T12:00:00Z",
                "secoes": [
                    {
                        "nome": "cubo",
                        "ordem": 0,
                        "slots": {"headline": self.texto_no_ar},
                    }
                ],
            },
        )

    def _listar(self, request):
        return httpx.Response(200, json=self.experimentos)

    def _achar(self, request) -> dict | None:
        alvo = request.url.path.rstrip("/").split("/")
        alvo = alvo[-2] if alvo[-1] == "estado" else alvo[-1]
        return next((e for e in self.experimentos if e["id"] == alvo), None)

    def _ler(self, request):
        achado = self._achar(request)
        if achado is None:
            return httpx.Response(404, json={"detail": "experimento inexistente"})
        if self.mudancas:
            return httpx.Response(200, json={**achado, **self.releitura})
        return httpx.Response(200, json=achado)

    def _criar(self, request):
        corpo = json.loads(request.content)
        self.criacoes += 1
        novo = self.experimento(
            "rascunho",
            hipotese=corpo["hipotese"],
            texto_b=corpo["variantes"][1]["valor"],
        )
        novo.update(
            taxa_base=corpo["taxa_base"],
            mde=corpo["mde"],
            dias_planejados=corpo["dias_planejados"],
            metrica_principal=corpo["metrica_principal"],
        )
        for variante, pedida in zip(novo["variantes"], corpo["variantes"]):
            variante["peso"] = pedida["peso"]
        self.corpo_criado = corpo
        return httpx.Response(201, json=novo)

    def _mudar(self, request):
        achado = self._achar(request)
        pedido = json.loads(request.content)
        self.mudancas.append((achado["id"], pedido))
        if pedido["estado"] == achado["estado"]:
            return httpx.Response(200, json=achado)
        if pedido["estado"] == "ativo":
            if any(e["estado"] == "ativo" for e in self.experimentos):
                return httpx.Response(
                    409, json={"detail": "já há um experimento no ar nesta página."}
                )
            # `services/catalogo/apps/paginas/api.py`: iniciar regrava `a` com o
            # texto publicado NESTE instante.
            self.texto_no_ar = self.publicar_ao_iniciar or self.texto_no_ar
            achado["variantes"][0]["valor"] = self.texto_no_ar
            achado.update(estado="ativo", iniciado_em="2026-09-27T11:00:00Z")
        else:
            achado.update(estado="encerrado", decisao=pedido["decisao"])
        return httpx.Response(200, json=achado)


def _rodar(acao: str, saida: StringIO | None = None) -> str:
    saida = saida or StringIO()
    call_command("semear_experimento", acao=acao, stdout=saida)
    return saida.getvalue()


def _parar(acao: str) -> tuple[str, str]:
    """A frase da parada e tudo o que saiu antes dela."""
    saida = StringIO()
    with pytest.raises(CommandError) as erro:
        _rodar(acao, saida)
    return str(erro.value), saida.getvalue()


def _linha_pronto(saida: str) -> str:
    (linha,) = [l for l in saida.splitlines() if l.startswith("PRONTO: ")]
    return linha


def _linhas_da_admin(frase: str) -> set[str]:
    """O nome de rota de cada link da frase, pelas rotas da admin."""
    nomes = set()
    for link in re.findall(r"https://\S+/", frase):
        partes = urlsplit(link)
        assert partes.netloc == HOST, link
        assert partes.path.startswith("/admin/"), link
        nomes.add(resolve(partes.path.removeprefix("/admin")).url_name)
    return nomes


# ---------------------------------------------------------------------------
# 1. Criar e iniciar
# ---------------------------------------------------------------------------
@respx.mock
def test_iniciar_cria_o_aa_com_a_assinatura_da_tela_e_poe_no_ar():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:291
    catalogo = CatalogoFalso()
    saida = _rodar("iniciar-aa")

    assert catalogo.corpo_criado == {
        "secao": "cubo",
        "slot": "headline",
        "hipotese": HIPOTESE,
        "metrica_principal": "cta_checkout",
        "taxa_base": 0.03,
        "mde": 0.01,
        "dias_planejados": 7,
        "variantes": [
            {"variante_id": "a", "peso": 5000},
            {"variante_id": "b", "peso": 5000, "valor": TITULO_NO_AR},
        ],
    }
    (criado,) = catalogo.experimentos
    assert criado["estado"] == "ativo"
    assert _linha_pronto(saida) == (
        f"PRONTO: A/A ativo em {HOST}, experimento {criado['id']}, estado ativo, "
        "2 variantes com o mesmo texto."
    )


@respx.mock
def test_iniciar_deixa_a_auditoria_das_duas_escritas_assinada_pelo_semeador():
    # guarda: services/admin/apps/core/experimentos.py:321
    catalogo = CatalogoFalso()
    _rodar("iniciar-aa")
    (criado,) = catalogo.experimentos

    linhas = list(Registro.objects.order_by("id"))
    assert [(r.acao, r.alvo, r.desfecho) for r in linhas] == [
        (Registro.CRIAR_EXPERIMENTO, criado["id"], Registro.OK),
        (Registro.INICIAR_EXPERIMENTO, criado["id"], Registro.OK),
    ]
    for linha in linhas:
        assert linha.quem_email == semear_experimento.ATOR.admin["email"]
        assert linha.quem_id == "pipeline:semear-experimento"
        assert linha.quem_email.endswith("@pipeline.invalid")


# ---------------------------------------------------------------------------
# 2. Idempotência
# ---------------------------------------------------------------------------
@respx.mock
def test_rodar_duas_vezes_nao_cria_segundo_experimento():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:253
    catalogo = CatalogoFalso()
    primeira = _linha_pronto(_rodar("iniciar-aa"))
    segunda = _linha_pronto(_rodar("iniciar-aa"))

    assert catalogo.criacoes == 1
    assert len(catalogo.experimentos) == 1
    assert primeira == segunda
    assert Registro.objects.count() == 2


# ---------------------------------------------------------------------------
# 3. Só a assinatura inteira é o A/A
# ---------------------------------------------------------------------------
@respx.mock
def test_outro_experimento_ativo_para_por_seguranca_sem_tocar_nele():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:256
    catalogo = CatalogoFalso()
    comum = catalogo.experimento(
        "ativo", hipotese="Falar de peça vendida vende mais", texto_b="Outro título"
    )

    frase, _ = _parar("iniciar-aa")

    assert frase.startswith("PAROU POR SEGURANÇA:")
    assert comum["id"] in frase
    assert "Encerrar" in frase
    assert _linhas_da_admin(frase) == {"decisao_do_experimento"}
    assert catalogo.criacoes == 0
    assert catalogo.mudancas == []
    assert comum["estado"] == "ativo"
    assert not Registro.objects.exists()


def _parecido_com_o_aa_para_sem_tocar(catalogo: CatalogoFalso, parecido: dict):
    frase, saida = _parar("iniciar-aa")

    assert frase.startswith("PAROU POR SEGURANÇA:") and parecido["id"] in frase
    assert "PRONTO:" not in saida
    assert _linha_pronto(_rodar("encerrar")).startswith("PRONTO: nada a encerrar")
    assert _linha_pronto(_rodar("medir")).startswith("PRONTO: nada a medir")
    assert catalogo.criacoes == 0
    assert catalogo.mudancas == []
    assert parecido["estado"] == "ativo"


@respx.mock
def test_experimento_com_a_hipotese_do_aa_e_textos_diferentes_nao_e_o_aa():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:149
    catalogo = CatalogoFalso()
    parecido = catalogo.experimento("ativo", texto_b="Um título diferente")
    _parecido_com_o_aa_para_sem_tocar(catalogo, parecido)


@respx.mock
def test_aa_com_a_mesma_hipotese_noutro_espaco_nao_e_o_aa():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:145
    catalogo = CatalogoFalso()
    parecido = catalogo.experimento("ativo", slot="subtitulo")
    _parecido_com_o_aa_para_sem_tocar(catalogo, parecido)


@respx.mock
def test_aa_de_variante_unica_nao_e_o_aa():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:147
    catalogo = CatalogoFalso()
    parecido = catalogo.experimento("ativo", variantes=1)
    _parecido_com_o_aa_para_sem_tocar(catalogo, parecido)


@respx.mock
@pytest.mark.parametrize("forma", ["tres-bracos", "pesos-90-10"])
def test_mesmo_texto_com_outra_divisao_nao_e_o_aa(forma):
    catalogo = CatalogoFalso()
    parecido = catalogo.experimento("ativo")
    if forma == "tres-bracos":
        parecido["variantes"] = [
            {"variante_id": "a", "peso": 4000, "valor": TITULO_NO_AR},
            {"variante_id": "b", "peso": 3000, "valor": TITULO_NO_AR},
            {"variante_id": "c", "peso": 3000, "valor": TITULO_NO_AR},
        ]
    else:
        parecido["variantes"][0]["peso"] = 9000
        parecido["variantes"][1]["peso"] = 1000

    _parecido_com_o_aa_para_sem_tocar(catalogo, parecido)


@respx.mock
def test_titulo_vazio_no_ar_para_com_o_que_fazer_e_nada_nasce():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:266
    catalogo = CatalogoFalso(texto_no_ar="   ")

    frase, saida = _parar("iniciar-aa")

    assert frase == semear_experimento.TITULO_VAZIO
    assert "cubo.headline está vazio" in frase and "publique o título" in frase
    assert _linhas_da_admin(frase) == {"pagina_de_venda"}
    assert "PRONTO:" not in saida
    assert catalogo.criacoes == 0
    assert not Registro.objects.exists()


# ---------------------------------------------------------------------------
# 4. Rascunho do A/A
# ---------------------------------------------------------------------------
@respx.mock
def test_aa_em_rascunho_e_iniciado_e_nao_duplicado():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:277
    catalogo = CatalogoFalso()
    rascunho = catalogo.experimento("rascunho")

    saida = _rodar("iniciar-aa")

    assert catalogo.criacoes == 0
    assert rascunho["estado"] == "ativo"
    assert rascunho["id"] in _linha_pronto(saida)
    assert [r.acao for r in Registro.objects.all()] == [Registro.INICIAR_EXPERIMENTO]


@respx.mock
def test_rascunho_do_aa_com_texto_velho_e_encerrado_e_um_novo_nasce():
    """Iniciar o rascunho velho poria no ar `a` novo contra `b` velho."""
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:275
    catalogo = CatalogoFalso()
    velho = catalogo.experimento(
        "rascunho", texto_a="Título antigo", texto_b="Título antigo"
    )

    _rodar("iniciar-aa")

    assert velho["estado"] == "encerrado" and velho["decisao"] == "encerrar"
    assert catalogo.criacoes == 1
    novo = catalogo.experimentos[0]
    assert novo["estado"] == "ativo"
    assert {v["valor"] for v in novo["variantes"]} == {TITULO_NO_AR}


# ---------------------------------------------------------------------------
# 5. Encerrar
# ---------------------------------------------------------------------------
@respx.mock
def test_encerrar_encerra_o_aa_com_a_decisao_encerrar_pelo_caminho_da_tela():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:326
    catalogo = CatalogoFalso()
    aa = catalogo.experimento("ativo")

    saida = _rodar("encerrar")

    assert catalogo.mudancas == [
        (aa["id"], {"estado": "encerrado", "decisao": "encerrar", "vencedora": None})
    ]
    assert _linha_pronto(saida) == (
        f"PRONTO: A/A encerrado em {HOST}, experimento {aa['id']}, estado "
        "encerrado, decisão encerrar."
    )
    (linha,) = Registro.objects.all()
    assert (linha.acao, linha.alvo, linha.desfecho) == (
        Registro.DECIDIR_EXPERIMENTO,
        aa["id"],
        Registro.OK,
    )
    assert linha.quem_id == "pipeline:semear-experimento"


@respx.mock
def test_encerrar_nunca_encerra_experimento_que_nao_e_o_aa():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:143
    catalogo = CatalogoFalso()
    comum = catalogo.experimento("ativo", hipotese="Falar de peça vendida vende mais")

    saida = _rodar("encerrar")

    assert comum["estado"] == "ativo"
    assert catalogo.mudancas == []
    assert _linha_pronto(saida).startswith(f"PRONTO: nada a encerrar em {HOST}")


@respx.mock
def test_encerrar_sem_aa_no_ar_sai_verde_sem_mudar_nada():
    catalogo = CatalogoFalso()

    saida = _rodar("encerrar")

    assert catalogo.mudancas == []
    assert not Registro.objects.exists()
    assert _linha_pronto(saida) == (
        f"PRONTO: nada a encerrar em {HOST}, nenhum A/A ativo na página "
        f"{SLUG_DA_PAGINA}. Nada foi alterado."
    )


# ---------------------------------------------------------------------------
# 6. A releitura morde
# ---------------------------------------------------------------------------
@respx.mock
@pytest.mark.parametrize(
    "releitura",
    [
        {"estado": "rascunho"},
        {"estado": "encerrado", "decisao": "encerrar"},
        {"hipotese": "Falar de peça vendida vende mais"},
        {"slot": "subtitulo"},
        {"variantes": [{"variante_id": "a", "peso": 10000, "valor": TITULO_NO_AR}]},
    ],
    ids=["outro-estado", "ja-encerrado", "outra-hipotese", "outro-espaco", "uma-so"],
)
def test_releitura_divergente_ao_ligar_para_sem_linha_pronto(releitura):
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:389
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:200
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:206
    catalogo = CatalogoFalso()
    catalogo.releitura = releitura

    frase, saida = _parar("iniciar-aa")

    (criado,) = catalogo.experimentos
    assert "PRONTO:" not in saida
    assert frase.startswith(f"Pedi o estado ativo ao A/A {criado['id']}")
    assert "nada foi dado como pronto" in frase
    assert _linhas_da_admin(frase) == {"decisao_do_experimento"}


@respx.mock
def test_releitura_com_decisao_diferente_ao_desligar_para_sem_linha_pronto():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:202
    catalogo = CatalogoFalso()
    aa = catalogo.experimento("ativo")
    catalogo.releitura = {"estado": "encerrado", "decisao": "reverter"}

    frase, saida = _parar("encerrar")

    assert "PRONTO:" not in saida
    assert frase.startswith(f"Pedi o estado encerrado ao A/A {aa['id']}")
    assert "decisão reverter" in frase


@respx.mock
def test_pagina_publicada_entre_a_leitura_e_o_inicio_para_dizendo_que_esta_no_ar():
    """O catálogo grava em `a` o título novo e `b` fica com o velho."""
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:204
    catalogo = CatalogoFalso()
    catalogo.publicar_ao_iniciar = "Título publicado no meio do caminho"

    frase, saida = _parar("iniciar-aa")

    (criado,) = catalogo.experimentos
    assert criado["estado"] == "ativo"
    assert "PRONTO:" not in saida
    assert frase.startswith("PAROU POR SEGURANÇA:")
    assert f"o experimento {criado['id']} ESTÁ NO AR com textos diferentes" in frase
    assert "Encerrar" in frase
    assert semear_experimento.tela_de_decisao(criado["id"]) in frase
    assert _linhas_da_admin(frase) == {"decisao_do_experimento"}
    # E o encerrar do comando não o reconhece mais, como a frase avisa.
    assert _linha_pronto(_rodar("encerrar")).startswith("PRONTO: nada a encerrar")


# ---------------------------------------------------------------------------
# 7. Um site só
# ---------------------------------------------------------------------------
@respx.mock
def test_o_host_nao_e_mais_um_argumento():
    CatalogoFalso()
    with pytest.raises(TypeError, match="host"):
        call_command("semear_experimento", host="outro.site", acao="iniciar-aa")


@respx.mock
@pytest.mark.parametrize("falha", ["404", "sem-rede"])
def test_site_ausente_para_com_as_duas_causas_e_o_que_fazer(falha):
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:231
    catalogo = CatalogoFalso(site=falha != "404")
    if falha == "sem-rede":
        respx.get(_do_contrato("getSiteByHost")).mock(
            side_effect=httpx.ConnectError("sem rede")
        )

    frase, saida = _parar("iniciar-aa")

    assert frase == semear_experimento.SEM_SITE
    assert HOST in frase and "não respondeu" in frase
    assert "não está cadastrado" in frase and "O QUE FAZER" in frase
    assert _linhas_da_admin(frase) == {"pagina_de_venda"}
    assert "PRONTO:" not in saida
    assert catalogo.criacoes == 0


def test_os_links_das_mensagens_sao_rotas_da_admin():
    alvo = str(uuid.uuid4())
    assert _linhas_da_admin(
        f"{semear_experimento.TELA_DA_PAGINA} "
        f"{semear_experimento.tela_de_decisao(alvo)} "
        f"{semear_experimento.tela_de_resultado(alvo)}"
    ) == {"pagina_de_venda", "decisao_do_experimento", "resultado_do_experimento"}


@respx.mock
def test_acao_fora_da_lista_e_recusada():
    CatalogoFalso()
    with pytest.raises(CommandError):
        _rodar("promover")


# ---------------------------------------------------------------------------
# 8. Medir
# ---------------------------------------------------------------------------
def _funil(variantes, *, coleta=True, trocados=0) -> dict:
    return {
        "site_id": SITE_ID,
        "de": "2026-09-27",
        "ate": "2026-09-29",
        "coleta": (
            {"primeiro": "2026-09-27T12:00:00Z", "ultimo": "2026-09-29T09:00:00Z"}
            if coleta
            else {"primeiro": None, "ultimo": None}
        ),
        "passos": [
            {"passo": passo, "visitantes": 0} for passo in MedicaoClient.PASSOS_DO_FUNIL
        ],
        "por_dia": [],
        "variantes": [
            {
                "variante_id": v,
                "atribuidos": at,
                "expostos": ex,
                "convertidos": co,
                "passos": [],
            }
            for v, at, ex, co in variantes
        ],
        "visitantes_com_bracos_trocados": trocados,
    }


def _nada_mudou(catalogo: CatalogoFalso) -> None:
    assert catalogo.mudancas == [] and catalogo.criacoes == 0
    assert not Registro.objects.exists()


@respx.mock
def test_medir_conta_por_braco_pelo_caminho_da_tela_de_resultado():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:374
    catalogo = CatalogoFalso()
    aa = catalogo.experimento("ativo")
    rota = respx.get(FUNIL).mock(
        return_value=httpx.Response(
            200, json=_funil([("a", 120, 110, 4), ("b", 118, 109, 5)], trocados=1)
        )
    )

    saida = _rodar("medir")

    pedido = rota.calls.last.request.url.params
    assert dict(pedido) == {
        "de": "2026-09-27",
        "ate": "2026-09-29",
        "site_id": SITE_ID,
        "experimento_id": aa["id"],
        "secao": "cubo",
    }
    linha = _linha_pronto(saida)
    assert linha.startswith(
        f"PRONTO: contagem do A/A {aa['id']} em {HOST}, janela 27/09/2026 a "
        "29/09/2026: a atribuidos=120 expostos=110 convertidos=4; "
        "b atribuidos=118 expostos=109 convertidos=5; trocados=1; srm atribuidos=ok"
    )
    assert linha.endswith("; veredito coletando")
    _nada_mudou(catalogo)


@respx.mock
def test_medir_sem_aa_ativo_diz_isso_sem_ler_a_medicao():
    catalogo = CatalogoFalso()
    catalogo.experimento("ativo", hipotese="Falar de peça vendida vende mais")
    rota = respx.get(FUNIL).mock(return_value=httpx.Response(500))

    saida = _rodar("medir")

    assert _linha_pronto(saida).startswith(f"PRONTO: nada a medir em {HOST}")
    assert "iniciar-aa" in saida
    assert not rota.called
    _nada_mudou(catalogo)


@respx.mock
@pytest.mark.parametrize(
    "resposta",
    [httpx.Response(503), httpx.ConnectError("sem rede")],
    ids=["503", "sem-rede"],
)
def test_medicao_fora_do_ar_para_por_seguranca_sem_pronto(resposta):
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:344
    catalogo = CatalogoFalso()
    aa = catalogo.experimento("ativo")
    if isinstance(resposta, Exception):
        respx.get(FUNIL).mock(side_effect=resposta)
    else:
        respx.get(FUNIL).mock(return_value=resposta)

    frase, saida = _parar("medir")

    assert frase.startswith(f"PAROU POR SEGURANÇA: a medição não respondeu")
    assert aa["id"] in frase and "O QUE FAZER" in frase
    assert _linhas_da_admin(frase) == {"resultado_do_experimento"}
    assert "PRONTO:" not in saida
    _nada_mudou(catalogo)


@respx.mock
def test_medicao_incoerente_para_por_seguranca_sem_pronto():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:346
    catalogo = CatalogoFalso()
    aa = catalogo.experimento("ativo")
    respx.get(FUNIL).mock(
        return_value=httpx.Response(200, json=_funil([("c", 10, 10, 1)]))
    )

    frase, saida = _parar("medir")

    assert frase.startswith("PAROU POR SEGURANÇA: a medição respondeu")
    assert aa["id"] in frase and "versão que o experimento não tem (c)" in frase
    assert "PRONTO:" not in saida
    _nada_mudou(catalogo)


@respx.mock
def test_medir_sem_evento_na_janela_mostra_os_zeros_medidos():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:349
    catalogo = CatalogoFalso()
    aa = catalogo.experimento("ativo")
    respx.get(FUNIL).mock(
        return_value=httpx.Response(200, json=_funil([], coleta=False))
    )

    saida = _rodar("medir")

    assert "Nenhum evento do funil chegou na janela." in saida
    assert _linha_pronto(saida) == (
        f"PRONTO: contagem do A/A {aa['id']} em {HOST}, janela 27/09/2026 a "
        "29/09/2026: a atribuidos=0 expostos=0 convertidos=0; "
        "b atribuidos=0 expostos=0 convertidos=0; trocados=0"
    )
    _nada_mudou(catalogo)
