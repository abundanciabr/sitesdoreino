import datetime as dt
import importlib
from types import SimpleNamespace

from django.apps import apps
from django.db import connection

from apps.core import ciclo_produtos, governanca, placar
from apps.core.models import CartaoDoPlacar, VersaoDoCartaoDoPlacar


def ficha(**dados):
    return dict(site_id="mesh", email="pessoa@example.com", origem="comprou",
                status="ativa", virou_aluno_em="2026-10-12T03:00:00Z", **dados)


def test_periodos_ignoram_recompra_e_base_anterior():
    dados = [ficha(), {**ficha(), "virou_aluno_em": "2026-11-14T15:00:00Z"},
             {**ficha(), "virou_aluno_em": "2026-09-01T12:00:00Z"},
             {**ficha(), "email": "outra@example.com", "virou_aluno_em": "2026-11-14T15:00:00Z"}]
    r = governanca.contar_alunos(dados, "mesh", dt.date(2026, 11, 14))
    assert r["total"] == 2 and r["vendas"] == 3 and r["mes"] == 1
    assert r["por_mes"] == {(2026, 10): 1, (2026, 11): 1}
    assert [p["total"] for p in r["periodos"]] == [1, 1, 1, 2, 2]


def test_filtro_por_produto_nao_depende_do_crm_e_nao_soma_pessoas():
    catalogo = SimpleNamespace(OK="ok", oferta_do_site=lambda site, slug:
        ("ok", {"product": {"id": "low" if slug.startswith("desafio") else "mid"}}))
    dados = [ficha(product_id="low"), ficha(product_id="mid"),
             {**ficha(product_id="mid"), "origem": "administrativo"},
             {**ficha(product_id="mid"), "origem": "teste"},
             {**ficha(product_id="mid"), "status": "reembolsada"},
             {**ficha(product_id="low"), "site_id": "outra"}]
    paineis = ciclo_produtos.paineis_do_site(dados, "mesh", dt.date(2026, 10, 14), catalogo)
    assert [p["total"] for p in paineis] == [1, 1]
    assert [p["atual"]["meta"] for p in paineis] == [0, 5]
    assert governanca.contar_alunos(dados, "mesh", dt.date(2026, 10, 14))["total"] == 1


def test_data_futura_nao_entra_no_resultado_de_hoje():
    dados = [{**ficha(), "virou_aluno_em": "2026-10-15T03:00:00Z"}]
    assert ciclo_produtos.montar_painel("curso", dados, dt.date(2026, 10, 14))["total"] == 0


def test_migracao_corrige_cartoes_e_preserva_revisoes_anteriores():
    cartao = CartaoDoPlacar.objects.get(nome="compras-no-ciclo")
    anteriores = list(cartao.versoes.values_list("id", "dados"))
    cartao.dados = {**cartao.dados, "alvo": 1000, "partida_em": "2026-09-03",
                    "ate": "2026-12-15", "semanas": []}
    cartao.save()
    migracao = importlib.import_module("apps.core.migrations.0050_coerencia_placar")
    migracao.atualizar(apps, SimpleNamespace(connection=connection))
    cartao.refresh_from_db()
    assert cartao.dados["alvo"] == 10000 and cartao.dados["ate"] == "2027-12-31"
    assert "semanas" not in cartao.dados
    assert list(cartao.versoes.filter(id__in=[v[0] for v in anteriores]).values_list("id", "dados")) == anteriores
    assert cartao.versoes.filter(dados__alvo=1000).exists()


def test_sem_curva_2027_nao_inventa_meta_mensal_ou_semanal():
    meta, avisos = placar.ler_cartao(placar.CARTAO_DA_META)
    assert not avisos
    r = placar.calcular_placar(meta, 0, dt.date(2026, 10, 14))
    assert r["veredito"] == "em-andamento" and r["distancia"] == 10000
    assert r["esperado_hoje"] is None
    mes, _ = placar.ler_cartao(placar.CARTAO_DO_MES)
    assert placar.calcular_o_mes(mes, meta, 0, dt.date(2026, 10, 14))["alvo"] is None


def test_montagem_atual_usa_mesmas_fichas_e_metas(monkeypatch):
    monkeypatch.setattr(placar.AlunosClient, "alunos", lambda self: [ficha()])
    monkeypatch.setattr(placar.AlunosClient, "fila", lambda *a: [])
    monkeypatch.setattr(placar.CatalogoClient, "oferta_do_site", lambda self, *a:
                        (self.OK, {"product": {"id": "sem-matricula"}}))
    ctx = placar.montar_o_placar(dt.date(2026, 10, 14), "mesh")
    assert ctx["placar"]["x"] == ctx["alunos_2027"]["total"] == ctx["barra"]["x"] == 1
    assert ctx["meta"]["ate"] == "2027-12-31"
    assert ctx["direcao"]["pedidos"]["meta"] is None
    assert ctx["doze"][0]["valor"] == 1
    assert "+1 na meta" not in (ctx["restricao"]["gesto"] or "")
