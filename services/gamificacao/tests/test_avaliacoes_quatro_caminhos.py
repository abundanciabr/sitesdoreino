"""A realização avaliada, a sequência e a unicidade dos bônus."""

import pytest
import gzip
import hashlib
import json
from datetime import date
from uuid import uuid4

from apps.core.perfil import perfil_de
from apps.gamificacao.bonus_faixas import configurar, conceder
from apps.gamificacao.jornada import registrar_avaliacao, situacao
from apps.gamificacao.models import (AvaliacaoDaJornada, BackupDoReinicioDasFaixas, FaixaDoAluno, JornadaPessoal,
                                     LancamentoDeXP, RecebimentoDeclarado, RegistroDaJornada)


pytestmark = pytest.mark.django_db
P, SITE = "aluna-avaliada", "site-avaliacoes"


@pytest.fixture(autouse=True)
def jornada_inicial(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    perfil_de(P, SITE)
    JornadaPessoal.objects.create(pessoa_id=P, site_id=SITE, inicio={"motivo": "ugc"})
    configurar(SITE)


def avaliar(ordem, resultado="reconhecida", chave=None):
    return registrar_avaliacao(P, SITE, ordem, resultado,
        f"A realização {ordem} foi examinada: {resultado}.",
        {"chave": chave or f"tentativa:{ordem}:{resultado}", "item": "acessório"})


def test_fora_de_ordem_espera_predecessoras_e_nao_duplica_xp():
    avaliar(7)
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    for ordem in range(2, 7):
        avaliar(ordem)
    assert situacao(P, SITE)["atual"]["ordem"] == 7
    assert len(situacao(P, SITE)["lista"]) == 7
    assert sum(x.pontos for x in LancamentoDeXP.objects.filter(
        pessoa_id=P, site_id=SITE, regra_slug__startswith="bonus-faixa-")) == 105000
    avaliar(7)
    assert AvaliacaoDaJornada.objects.filter(pessoa_id=P, site_id=SITE).count() == 6


def test_incompleta_falha_e_repeticao_nao_revogam_conquista():
    avaliar(2, "incompleta")
    avaliar(2, "falha")
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    avaliar(2)
    avaliar(2, "falha", "falha-posterior")
    assert situacao(P, SITE)["atual"]["ordem"] == 2
    assert AvaliacaoDaJornada.objects.filter(pessoa_id=P, site_id=SITE, ordem=2).count() == 4


def test_trocar_caminho_preserva_conquista_sem_repetir_bonus():
    for ordem in range(2, 6):
        avaliar(ordem)
    j = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    j.inicio = {"motivo": "jogo"}
    j.save(update_fields=["inicio"])
    assert situacao(P, SITE)["atual"]["ordem"] == 5
    antes = LancamentoDeXP.objects.filter(pessoa_id=P, site_id=SITE).count()
    avaliar(5, chave="pratica-jogo")
    assert situacao(P, SITE)["atual"]["ordem"] == 5
    assert LancamentoDeXP.objects.filter(pessoa_id=P, site_id=SITE).count() == antes


def test_recebimento_so_avanca_com_vinculo_visivel_e_atinge_varios_graus(monkeypatch):
    from apps.gamificacao import prints_recebimentos as prints

    j = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    j.inicio, j.meta_cents = {"motivo": "freelancer"}, 10000
    j.save(update_fields=["inicio", "meta_cents"])
    for ordem in range(2, 7):
        avaliar(ordem)
    r = RecebimentoDeclarado.objects.create(
        pessoa_id=P, site_id=SITE, chave=uuid4(), origem="fora",
        estado="pendente", valor_cents=10000, valor_original_cents=10000,
        moeda_original="BRL", recebido_em=date(2026, 10, 1),
        print_bytes=b"imagem-privada", print_sha256="a" * 64,
        referencia_trabalho="pedido-1234",
    )
    leitura = {"status": "recebido", "valor_cents": 10000, "moeda": "BRL",
               "data": "2026-10-01", "identificador_trabalho": "pedido-1234"}
    monkeypatch.setattr(prints, "ler_modelo", lambda *_: {**leitura})
    assert prints.processar(r.pk)
    assert situacao(P, SITE)["atual"]["ordem"] == 13
    assert sum(x.pontos for x in LancamentoDeXP.objects.filter(
        pessoa_id=P, site_id=SITE, regra_slug__startswith="bonus-faixa-")) == 720000
    assert prints._mesmo_trabalho("pedido-1234", "outro-pedido") is False


def test_grau_antigo_pago_preserva_baseline_sem_pagar_passos_inferidos():
    assert conceder(P, SITE, [13]) == 200000
    s = situacao(P, SITE)
    assert s["atual"]["ordem"] == 7
    assert s["graus_historicos"][-1]["ordem"] == 13
    avaliar(2)
    assert sum(x.pontos for x in LancamentoDeXP.objects.filter(
        pessoa_id=P, site_id=SITE, regra_slug__startswith="bonus-faixa-")) == 200000


def test_backup_privado_preserva_grau_e_credito_equivalente_apos_limpeza():
    from django.utils import timezone
    from apps.gamificacao.historico_reinicio import _extrair

    agora = timezone.now()
    linhas = [
        {"model": "gamificacao.lancamentodexp", "fields": {
            "pessoa": P, "status": "definitivo", "pontos": 10000,
            "regra_slug": "bonus-faixa-azul", "criado_em": agora.isoformat()}},
        {"model": "gamificacao.lancamentodexp", "fields": {
            "pessoa": P, "status": "definitivo", "pontos": 200000,
            "regra_slug": "bonus-faixa-preta-grau-7", "criado_em": agora.isoformat()}},
        {"model": "gamificacao.faixadoaluno", "fields": {
            "pessoa": P, "ordem": 3, "origem": "sandbox"}},
        {"model": "gamificacao.registrodajornada", "fields": {
            "pessoa": P, "acao": "conclusao", "dados": {"passo": 3}}},
    ]
    conteudo = gzip.compress(json.dumps(linhas).encode(), mtime=0)
    BackupDoReinicioDasFaixas.objects.create(
        site_id=SITE, chave="reinicio-autorizado-20261011", conteudo=conteudo,
        sha256=hashlib.sha256(conteudo).hexdigest(), contagens={},
        criado_em=agora, aplicado_em=agora,
    )
    _extrair.cache_clear()
    j = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    j.inicio = {"motivo": "freelancer"}
    j.save(update_fields=["inicio"])
    assert situacao(P, SITE)["atual"]["ordem"] == 13
    assert situacao(P, SITE)["graus_historicos"][-1]["ordem"] == 13
    assert registrar_avaliacao(P, SITE, 5, "reconhecida", "Sandbox examinado e aprovado.", {
        "chave": "backup:sandbox:1", "trabalho_id": "1", "entrega_id": "2",
        "analise_id": "3", "conquista_equivalente_original": {"ordem": 3, "origem": "sandbox"},
    })["bonus_xp"] == 0
    assert AvaliacaoDaJornada.objects.get(ordem=5).evidencia["credito_equivalente_confirmado"]
    assert not LancamentoDeXP.objects.filter(pessoa_id=P, site_id=SITE,
        regra_slug__startswith="bonus-faixa-").exists()


def test_comprovante_exige_avaliacao_reconhecida_da_mesma_ordem():
    from apps.gamificacao.bonus_inicio import comprovante, conferir_comprovante

    assert conceder(P, SITE, [2]) == 5000
    token = comprovante(P, SITE, 2, 0, 5000)
    assert conferir_comprovante(token, P, SITE, 2) is None
    avaliar(2)
    token = comprovante(P, SITE, 2, 0, 5000)
    assert conferir_comprovante(token, P, SITE, 2) == (0, 5000)
    assert conferir_comprovante(token, P, SITE, 3) is None


def test_print_sem_vinculo_do_trabalho_pede_esclarecimento(monkeypatch):
    from apps.gamificacao import prints_recebimentos as prints

    j = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    j.inicio = {"motivo": "freelancer"}
    j.save(update_fields=["inicio"])
    r = RecebimentoDeclarado.objects.create(
        pessoa_id=P, site_id=SITE, chave=uuid4(), origem="fora",
        estado="pendente", valor_cents=1000, valor_original_cents=1000,
        moeda_original="BRL", recebido_em=date(2026, 10, 1),
        print_bytes=b"imagem-privada", print_sha256="b" * 64,
        referencia_trabalho="pedido-1234",
    )
    monkeypatch.setattr(prints, "ler_modelo", lambda *_: {
        "status": "recebido", "valor_cents": 1000, "moeda": "BRL",
        "data": "2026-10-01", "identificador_trabalho": None,
    })
    assert prints.processar(r.pk) is False
    r.refresh_from_db()
    assert r.estado == "esclarecer" and r.leitura["motivo"] == "trabalho"
    assert not AvaliacaoDaJornada.objects.filter(pessoa_id=P, site_id=SITE, ordem=7).exists()


@pytest.mark.parametrize("caminho,palavra", [
    ("ugc", "acessório"), ("jogo", "objeto"), ("aprender", "cor"),
    ("freelancer", "Sandbox"),
])
def test_checklist_mostra_atividade_do_caminho(caminho, palavra):
    from apps.gamificacao.checklist_trilha import montar_checklists

    j = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    j.inicio = {"motivo": caminho}
    j.save(update_fields=["inicio"])
    s = situacao(P, SITE)
    checklist = montar_checklists(P, SITE, s)
    assert palavra in checklist[5]["itens"][0]["titulo"]
    assert s["proxima_url"].startswith("/trilha/")
    assert checklist[5]["itens"][0]["acao"]["url"].startswith("/trilha/")
    assert len(s["lista"]) == (13 if caminho == "freelancer" else 7)
    assert [i["id"] for i in checklist[2]["itens"]] == ["motivo-2", "plano-2"]


def _fato_sandbox(*, teste=False, atende=True):
    return {
        "origem": "sandbox", "pessoa_id": P, "site_id": SITE,
        "estado": "concluida", "teste_mantenedor": teste,
        "trabalho_id": "trabalho-1", "entrega_id": "entrega-1", "analise_id": "analise-1",
        "resultado": {
            "avaliacao": {"resultado": "atende" if atende else "inconclusiva",
                          "justificativa": "O modelo.glb foi examinado e atendeu ao pedido."},
            "tem_falhas": False,
            "medidas_programas": [{"arquivo": "modelo.glb", "estado": "concluida",
                                   "conteudo": {"arquivos": ["malha"]}}],
            "requisitos": [{"encontrado": "Forma solicitada", "nao_encontrado": "",
                            "inconclusivo": "", "evidencias": ["modelo.glb: forma"]}],
        },
    }


def test_recupera_analise_real_fora_de_ordem_sem_repetir_bonus_historico():
    from apps.gamificacao.jornada import recuperar_avaliacoes_anteriores
    from django.utils import timezone

    j = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    j.inicio = {"motivo": "freelancer"}
    j.save(update_fields=["inicio"])
    FaixaDoAluno.objects.create(pessoa_id=P, site_id=SITE, ordem=3,
        estado="alcancada", origem="sandbox", alcancada_em=timezone.now())
    RegistroDaJornada.objects.create(pessoa_id=P, site_id=SITE,
        acao="conclusao", dados={"passo": 3})
    assert conceder(P, SITE, [3]) == 10000
    avaliar(4)
    total_antes = sum(x.pontos for x in LancamentoDeXP.objects.filter(pessoa_id=P, site_id=SITE))
    assert recuperar_avaliacoes_anteriores(P, SITE, [_fato_sandbox()]) == 1
    assert situacao(P, SITE)["atual"]["ordem"] == 5
    assert AvaliacaoDaJornada.objects.get(ordem=5).evidencia["credito_equivalente_confirmado"]
    assert sum(x.pontos for x in LancamentoDeXP.objects.filter(pessoa_id=P, site_id=SITE)) == total_antes
    assert recuperar_avaliacoes_anteriores(P, SITE, [_fato_sandbox()]) == 0


def test_recuperacao_descarta_teste_e_analise_inconclusiva():
    from apps.gamificacao.jornada import recuperar_avaliacoes_anteriores

    j = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    j.inicio = {"motivo": "freelancer"}
    j.save(update_fields=["inicio"])
    assert recuperar_avaliacoes_anteriores(P, SITE, [
        _fato_sandbox(teste=True), _fato_sandbox(atende=False),
        {**_fato_sandbox(), "estado": "falha"},
    ]) == 0
    assert not AvaliacaoDaJornada.objects.exists()


def test_fila_historica_exige_aceite_expresso_do_cliente_e_espera_sequencia():
    from apps.gamificacao.jornada import recuperar_avaliacoes_anteriores

    j = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    j.inicio = {"motivo": "freelancer"}
    j.save(update_fields=["inicio"])
    fato = {"origem": "fila", "pessoa_id": P, "site_id": SITE,
            "resultado": "reconhecida", "feedback": "O cliente aceitou a versão 2.",
            "evidencia": {"pedido_id": "pedido-7", "entrega_id": "entrega-2",
                          "versao": 2, "aprovada_em": "2026-10-11T10:00:00Z",
                          "avaliador_papel": "cliente"}}
    falso = {**fato, "evidencia": {**fato["evidencia"], "avaliador_papel": "equipe"}}
    assert recuperar_avaliacoes_anteriores(P, SITE, [falso]) == 0
    assert recuperar_avaliacoes_anteriores(P, SITE, [fato]) == 1
    assert situacao(P, SITE)["atual"]["ordem"] == 1
    for ordem in range(2, 6):
        avaliar(ordem)
    assert situacao(P, SITE)["atual"]["ordem"] == 6
    assert recuperar_avaliacoes_anteriores(P, SITE, [fato]) == 0
