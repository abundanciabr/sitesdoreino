from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.gamificacao.handlers import ao_sandbox_avaliacao_atualizada, ao_sandbox_trabalho_concluido
from apps.gamificacao.models import AvaliacaoDaJornada, AvaliacaoSandboxProjetada, BackupDoReinicioDasFaixas, JornadaPessoal, LancamentoDeXP, RegistroDaJornada
from apps.gamificacao.sandbox_avaliacoes import resumo
from tests.test_conclusao_sandbox_xp import preparar_ate


def evento(*, versao=1, estado="concluida", resultado="atende", atual=True,
           historico=False, trabalho_id="trabalho-a", pessoa_id="aluno-concluiu",
           site_id="escola-teste", atualizado_em=None, entrega_criada_em=None):
    instante = atualizado_em or timezone.now().isoformat()
    return {
        "event": "encomendas.sandbox-avaliacao-atualizada", "version": 1,
        "event_id": str(uuid4()), "occurred_at": instante,
        "data": {
            "site_id": site_id, "pessoa_id": pessoa_id, "trabalho_id": trabalho_id,
            "entrega_id": f"entrega-{versao}", "analise_id": f"analise-{versao}",
            "versao": versao, "entrega_criada_em": entrega_criada_em or instante,
            "atualizado_em": instante, "ocorrido_em": instante,
            "atual": atual, "historico": historico, "estado": estado,
            "resultado": resultado, "explicacao": "A peça atendeu ao pedido.",
            "justificativa": "A geometria está íntegra.",
            "proxima_acao": "Siga para a próxima prática.",
            "url": "/encomendas/sandbox/trabalho-a/",
        },
    }


@pytest.fixture(autouse=True)
def sem_relay(monkeypatch):
    from apps.gamificacao import motor
    monkeypatch.setattr(motor, "relay_apos_commit", lambda: None)


@pytest.mark.django_db
def test_projecao_de_analise_real_nao_concede_faixa_por_si():
    preparar_ate()
    ao_sandbox_trabalho_concluido({"event": "encomendas.sandbox-trabalho-concluido",
                                   "version": 1, "data": {"site_id": "escola-teste", "pessoa_id": "aluno-concluiu"}})
    assert not LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul").exists()
    pendente = evento(estado="pendente", resultado="")
    ao_sandbox_avaliacao_atualizada(pendente)
    assert resumo("aluno-concluiu", "escola-teste")["avaliacoes"][0]["reconhecimento"]["estado"] == "aguardando_analise"
    concluida = evento(atualizado_em=timezone.now().isoformat(),
                      entrega_criada_em=pendente["data"]["entrega_criada_em"])
    ao_sandbox_avaliacao_atualizada(concluida)
    ao_sandbox_avaliacao_atualizada(concluida)
    assert not LancamentoDeXP.objects.filter(regra_slug__startswith="bonus-faixa-").exists()
    assert not RegistroDaJornada.objects.filter(acao="avaliacao_sandbox").exists()
    assert resumo("aluno-concluiu", "escola-teste")["avaliacoes"][0]["reconhecimento"]["estado"] == "aguardando_sequencia"


@pytest.mark.django_db
def test_avaliacao_real_concede_verde_uma_vez_e_preserva_azul_do_item():
    from apps.core.perfil import perfil_de
    from apps.gamificacao.bonus_faixas import configurar
    from apps.gamificacao.jornada import registrar_avaliacao, situacao

    pessoa, site = "aluno-concluiu", "escola-teste"
    perfil_de(pessoa, site)
    JornadaPessoal.objects.create(pessoa_id=pessoa, site_id=site,
                                  inicio={"motivo": "freelancer"})
    configurar(site)
    for ordem in (2, 3, 4):
        registrar_avaliacao(pessoa, site, ordem, "reconhecida",
                            f"A realização {ordem} foi examinada com resultado positivo.",
                            {"chave": f"atividade:{ordem}", "fato": "material examinado"})
    azul_antes = LancamentoDeXP.objects.filter(
        pessoa_id=pessoa, site_id=site, regra_slug="bonus-faixa-azul",
    ).count()
    fato = {"event": "encomendas.sandbox-trabalho-concluido", "version": 1,
            "event_id": str(uuid4()), "occurred_at": timezone.now().isoformat(),
            "data": {"site_id": site, "pessoa_id": pessoa, "resultado": "reconhecida",
                     "feedback": "A análise concluiu que a geometria atende ao briefing da prática.",
                     "evidencia": {"chave": "sandbox:analise-real", "trabalho_id": "trabalho-real",
                                   "entrega_id": "entrega-real", "analise_id": "analise-real",
                                   "avaliacao": {"resultado": "atende"},
                                   "requisitos": [{"encontrado": True}],
                                   "imagens_examinadas": ["imagem-do-item"]}}}
    ao_sandbox_trabalho_concluido(fato)
    ao_sandbox_trabalho_concluido(fato)
    assert situacao(pessoa, site)["atual"]["ordem"] == 5
    assert AvaliacaoDaJornada.objects.filter(pessoa_id=pessoa, site_id=site, ordem=5).count() == 1
    assert LancamentoDeXP.objects.filter(
        pessoa_id=pessoa, site_id=site, regra_slug="bonus-faixa-verde",
    ).count() == 1
    assert LancamentoDeXP.objects.filter(
        pessoa_id=pessoa, site_id=site, regra_slug="bonus-faixa-azul",
    ).count() == azul_antes


@pytest.mark.django_db
def test_azul_antiga_do_sandbox_permanece_e_nao_recompensa_a_mesma_analise():
    from apps.core.perfil import perfil_de
    from apps.gamificacao.bonus_faixas import conceder, configurar
    from apps.gamificacao.jornada import registrar_avaliacao, situacao

    pessoa, site = "aluno-concluiu", "escola-teste"
    perfil_de(pessoa, site)
    JornadaPessoal.objects.create(pessoa_id=pessoa, site_id=site,
                                  inicio={"motivo": "freelancer"})
    configurar(site)
    evento_antigo = evento()
    ao_sandbox_avaliacao_atualizada(evento_antigo)
    projecao = AvaliacaoSandboxProjetada.objects.get(pessoa_id=pessoa, site_id=site)
    projecao.reconhecida_em = timezone.now()
    projecao.reconhecida_analise_id = projecao.analise_id
    projecao.save(update_fields=["reconhecida_em", "reconhecida_analise_id"])
    RegistroDaJornada.objects.create(pessoa_id=pessoa, site_id=site,
        acao="avaliacao_sandbox", dados={"analise_id": projecao.analise_id})
    assert conceder(pessoa, site, [3]) == 10000
    assert situacao(pessoa, site)["atual"]["ordem"] == 3
    for ordem in (2, 4):
        registrar_avaliacao(pessoa, site, ordem, "reconhecida",
                            f"A realização {ordem} foi examinada e reconhecida.",
                            {"chave": f"nova:{ordem}", "fato": "material examinado"})
    antes = sum(LancamentoDeXP.objects.filter(pessoa_id=pessoa, site_id=site)
                .values_list("pontos", flat=True))
    registrar_avaliacao(pessoa, site, 5, "reconhecida",
                        "A análise anterior reconheceu a prática realizada no Sandbox.",
                        {"chave": "historico:sandbox:" + projecao.analise_id,
                         "analise_id": projecao.analise_id,
                         "conquista_equivalente_original": {"ordem": 3, "origem": "sandbox"}})
    assert situacao(pessoa, site)["atual"]["ordem"] == 5
    assert sum(LancamentoDeXP.objects.filter(pessoa_id=pessoa, site_id=site)
               .values_list("pontos", flat=True)) == antes
    assert not LancamentoDeXP.objects.filter(pessoa_id=pessoa, site_id=site,
        regra_slug="bonus-faixa-verde").exists()


@pytest.mark.django_db
def test_falha_inconclusiva_historico_e_nao_atual_nao_creditam():
    preparar_ate()
    casos = [
        evento(estado="falha", resultado=""),
        evento(resultado="inconclusiva", trabalho_id="b"),
        evento(historico=True, trabalho_id="c"),
        evento(atual=False, trabalho_id="d"),
    ]
    for item in casos:
        ao_sandbox_avaliacao_atualizada(item)
    assert not LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul").exists()
    assert AvaliacaoSandboxProjetada.objects.count() == 4


@pytest.mark.django_db
def test_avaliacao_antes_da_etapa_dois_fica_registrada_e_espera_sequencia():
    ao_sandbox_avaliacao_atualizada(evento())
    assert resumo("aluno-concluiu", "escola-teste")["avaliacoes"][0]["reconhecimento"]["estado"] == "aguardando_sequencia"
    preparar_ate()
    assert not LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul").exists()


@pytest.mark.django_db
def test_nova_versao_pendente_nao_desfaz_bonus_nem_diz_que_foi_reconhecida():
    preparar_ate()
    antiga = evento()
    ao_sandbox_avaliacao_atualizada(antiga)
    nova = evento(versao=2, estado="pendente", resultado="")
    ao_sandbox_avaliacao_atualizada(nova)
    ao_sandbox_avaliacao_atualizada(antiga)
    linha = AvaliacaoSandboxProjetada.objects.get(trabalho_id="trabalho-a")
    assert linha.versao == 2 and linha.reconhecida_versao is None
    assert resumo("aluno-concluiu", "escola-teste")["avaliacoes"][0]["reconhecimento"]["estado"] == "aguardando_analise"
    assert not LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul").exists()


@pytest.mark.django_db
def test_limpeza_reinicia_numero_da_versao_mas_entrega_mais_nova_prevalece():
    preparar_ate()
    antiga = evento(versao=3)
    ao_sandbox_avaliacao_atualizada(antiga)
    nova = evento(versao=1, estado="pendente", resultado="")
    ao_sandbox_avaliacao_atualizada(nova)
    ao_sandbox_avaliacao_atualizada(antiga)
    linha = AvaliacaoSandboxProjetada.objects.get(trabalho_id="trabalho-a")
    assert linha.versao == 1 and linha.entrega_id == "entrega-1"
    assert linha.reconhecida_versao is None
    assert resumo("aluno-concluiu", "escola-teste")["avaliacoes"][0]["reconhecimento"]["estado"] == "aguardando_analise"
    assert not LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul").exists()


@pytest.mark.django_db
def test_evento_antigo_atrasado_apos_reinicio_nao_recria_bonus():
    preparar_ate()
    corte = timezone.now()
    BackupDoReinicioDasFaixas.objects.create(
        site_id="escola-teste", chave="reinicio-autorizado-20261011",
        conteudo=b"teste", sha256="teste", criado_em=corte, aplicado_em=corte,
    )
    antigo = evento(atualizado_em=(corte - timedelta(minutes=1)).isoformat())
    ao_sandbox_avaliacao_atualizada(antigo)
    linha = AvaliacaoSandboxProjetada.objects.get(trabalho_id="trabalho-a")
    assert linha.anterior_reinicio and linha.reconhecida_em is None
    assert not LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul").exists()


@pytest.mark.django_db
def test_declaracao_manual_da_terceira_etapa_nao_contorna_analise():
    from apps.gamificacao import jornada
    preparar_ate()
    with pytest.raises(ValueError, match="análise"):
        jornada.salvar("aluno-concluiu", "escola-teste", {
            "acao": "declaracao", "passo": 3, "estado": "feito",
            "revisao": jornada.situacao("aluno-concluiu", "escola-teste")["revisao"],
        })
    assert not LancamentoDeXP.objects.filter(regra_slug="bonus-faixa-azul").exists()


@pytest.mark.django_db
def test_token_de_par_nao_le_feedback_privado_de_outra_pessoa(client, monkeypatch, settings):
    settings.TOKENS_ACEITOS = {"token-par", "token-admin"}
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    monkeypatch.setenv("SITE_ID", "escola-teste")
    ao_sandbox_avaliacao_atualizada(evento())
    comum = client.get(
        "/api/gamificacao/trilha-do-aluno",
        {"pessoa_id": "aluno-concluiu", "site_id": "escola-teste"},
        HTTP_AUTHORIZATION="Bearer token-par",
    )
    assert comum.status_code == 200
    assert comum.json()["avaliacoes_sandbox"] == []
    reservado = client.get(
        "/api/gamificacao/jornada-sandbox/escola-teste/aluno-concluiu",
        HTTP_AUTHORIZATION="Bearer token-par",
    )
    assert reservado.status_code == 403
    admin = client.get(
        "/api/gamificacao/jornada-sandbox/escola-teste/aluno-concluiu",
        HTTP_AUTHORIZATION="Bearer token-admin",
    )
    assert admin.status_code == 200
    assert admin.json()["avaliacoes"][0]["explicacao"] == "A peça atendeu ao pedido."
