"""`manage.py semear_experimento`: o A/A técnico da oferta ligado e desligado pelo pipeline.

O comando é a segunda porta das mesmas regras da tela `/admin/paginas/experimentos/`
e da decisão do experimento, para o robô rodar o ensaio sem navegador e sem login.
O catálogo falso aqui guarda estado, nos endereços do contrato, para que rodar
duas vezes seja de fato rodar duas vezes contra o mesmo catálogo. Os guardas:

1. **Criar e iniciar com a assinatura certa**: hipótese exata, `a` sem texto (o
   catálogo grava o publicado), `b` com o texto publicado, 5000/5000, taxa base
   3%, efeito mínimo 1 ponto, 7 dias, métrica da tela. Auditoria das duas
   escritas, assinada pelo semeador e sem dado pessoal.
2. **Idempotência**: rodar de novo com o A/A no ar não cria nada e diz PRONTO.
3. **Outro experimento ativo faz parar**, sem tocar nele.
4. **A/A em rascunho é iniciado**, sem nascer um segundo.
5. **Encerrar só encerra o A/A**, com a decisão `encerrar`, e nunca um
   experimento comum. Sem A/A no ar, sai verde sem mudar nada.
6. **Host ausente ou desconhecido para** com o que fazer.
"""

from __future__ import annotations

import json
import uuid
from io import StringIO
from pathlib import Path

import httpx
import pytest
import respx
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.auditoria.models import Registro
from apps.core.management.commands import semear_experimento
from apps.core.paginas import SLUG_DA_PAGINA

CATALOGO = "http://catalogo:8000/api/catalogo"
HOST = "meshcraft.top"
SITE_ID = "site-mesh"
TITULO_NO_AR = "Modele para imprimir, do primeiro cubo à peça vendida"
HIPOTESE = "A/A técnico: mede sorteio, exposição e contagem, não conversão"
CONTRATO = yaml.safe_load(
    (
        Path(__file__).resolve().parents[3] / "contracts" / "catalogo.openapi.yaml"
    ).read_text(encoding="utf-8")
)


def _do_contrato(operacao: str) -> str:
    """O endereço da operação como o contrato o escreve, com o id como padrão."""
    (caminho,) = [
        caminho
        for caminho, verbos in CONTRATO["paths"].items()
        if any(v.get("operationId") == operacao for v in verbos.values())
    ]
    return CATALOGO + caminho.format(
        host=HOST,
        site_id=SITE_ID,
        slug=SLUG_DA_PAGINA,
        experimento_id="{experimento_id}",
    )


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")


class CatalogoFalso:
    """O catálogo, com memória: cria, lista, lê e muda estado como o de verdade."""

    def __init__(self, texto_no_ar: str = TITULO_NO_AR):
        self.texto_no_ar = texto_no_ar
        self.experimentos: list[dict] = []
        self.criacoes = 0
        self.mudancas: list[tuple[str, dict]] = []
        respx.get(_do_contrato("getSiteByHost")).mock(
            return_value=httpx.Response(
                200, json={"id": SITE_ID, "host": HOST, "name": "Meshcraft"}
            )
        )
        respx.get(f"{CATALOGO}/sites/by-host/outro.site").mock(
            return_value=httpx.Response(404, json={"detail": "site inexistente"})
        )
        respx.get(_do_contrato("getPage")).mock(side_effect=self._pagina)
        lista = _do_contrato("listExperiments")
        respx.get(lista).mock(side_effect=self._listar)
        respx.post(lista).mock(side_effect=self._criar)
        um = _do_contrato("getExperiment").replace("{experimento_id}", "")
        respx.get(url__regex=rf"^{um}[0-9a-f-]+$").mock(side_effect=self._ler)
        respx.post(url__regex=rf"^{um}[0-9a-f-]+/estado$").mock(side_effect=self._mudar)

    def experimento(self, estado, *, hipotese=HIPOTESE, texto_b=None, texto_a=None):
        corpo = {
            "id": str(uuid.uuid4()),
            "site_id": SITE_ID,
            "slug": SLUG_DA_PAGINA,
            "secao": "cubo",
            "slot": "headline",
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
            "iniciado_em": None,
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
            ],
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
            achado["variantes"][0]["valor"] = self.texto_no_ar
            achado.update(estado="ativo", iniciado_em="2026-09-27T11:00:00Z")
        else:
            achado.update(estado="encerrado", decisao=pedido["decisao"])
        return httpx.Response(200, json=achado)


def _rodar(acao: str, host: str = HOST) -> str:
    saida = StringIO()
    call_command("semear_experimento", host=host, acao=acao, stdout=saida)
    return saida.getvalue()


def _linha_pronto(saida: str) -> str:
    (linha,) = [l for l in saida.splitlines() if l.startswith("PRONTO: ")]
    return linha


# ---------------------------------------------------------------------------
# 1. Criar e iniciar
# ---------------------------------------------------------------------------
@respx.mock
def test_iniciar_cria_o_aa_com_a_assinatura_da_tela_e_poe_no_ar():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:192
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
    # guarda: services/admin/apps/core/experimentos.py:317
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
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:150
    catalogo = CatalogoFalso()
    primeira = _linha_pronto(_rodar("iniciar-aa"))
    segunda = _linha_pronto(_rodar("iniciar-aa"))

    assert catalogo.criacoes == 1
    assert len(catalogo.experimentos) == 1
    assert primeira == segunda
    assert Registro.objects.count() == 2


# ---------------------------------------------------------------------------
# 3. Outro experimento ativo
# ---------------------------------------------------------------------------
@respx.mock
def test_outro_experimento_ativo_para_por_seguranca_sem_tocar_nele():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:152
    catalogo = CatalogoFalso()
    comum = catalogo.experimento(
        "ativo", hipotese="Falar de peça vendida vende mais", texto_b="Outro título"
    )

    with pytest.raises(CommandError) as erro:
        _rodar("iniciar-aa")

    frase = str(erro.value)
    assert frase.startswith("PAROU POR SEGURANÇA:")
    assert comum["id"] in frase
    assert "Encerrar" in frase
    assert catalogo.criacoes == 0
    assert catalogo.mudancas == []
    assert comum["estado"] == "ativo"
    assert not Registro.objects.exists()


@respx.mock
def test_experimento_com_a_hipotese_do_aa_e_textos_diferentes_nao_e_o_aa():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:91
    catalogo = CatalogoFalso()
    parecido = catalogo.experimento("ativo", texto_b="Um título diferente")

    with pytest.raises(CommandError):
        _rodar("iniciar-aa")

    assert catalogo.criacoes == 0
    assert parecido["estado"] == "ativo"


# ---------------------------------------------------------------------------
# 4. Rascunho do A/A
# ---------------------------------------------------------------------------
@respx.mock
def test_aa_em_rascunho_e_iniciado_e_nao_duplicado():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:178
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
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:176
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
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:230
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
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:88
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
# 6. Host
# ---------------------------------------------------------------------------
@respx.mock
def test_sem_host_para_e_diz_o_que_fazer():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:126
    CatalogoFalso()
    with pytest.raises(CommandError) as erro:
        _rodar("iniciar-aa", host="")
    assert "--host" in str(erro.value) and "meshcraft.top" in str(erro.value)
    assert not Registro.objects.exists()


@respx.mock
def test_host_desconhecido_para_e_diz_o_que_fazer():
    # guarda: services/admin/apps/core/management/commands/semear_experimento.py:129
    catalogo = CatalogoFalso()
    with pytest.raises(CommandError) as erro:
        _rodar("iniciar-aa", host="outro.site")
    frase = str(erro.value)
    assert "outro.site" in frase and "Nada foi alterado" in frase
    assert "O QUE FAZER" in frase
    assert catalogo.criacoes == 0


@respx.mock
def test_acao_fora_da_lista_e_recusada():
    CatalogoFalso()
    with pytest.raises(CommandError):
        _rodar("promover")
