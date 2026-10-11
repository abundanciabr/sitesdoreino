import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory
from django.utils import timezone

from apps.agentes import super_equipe_operacao as op, super_equipe_desenvolvimento as dev
from apps.agentes.models import RotinaSuperEquipe, MelhoriaSuperEquipe, Execucao, Consumo
from apps.agentes.views_super_equipe import super_equipe_executor, super_equipe_fila
from tests.test_super_equipe_automatica import rotina, fontes, rodar, adiantar, melhoria


def requisicao(dados, admin=True):
    r = RequestFactory().post("/", data=json.dumps(dados), content_type="application/json")
    r.admin = {"robo": True} if admin else None
    return r


def test_contato_nao_inventa_acao_e_rejeita_nao_admin(rotina):
    assert super_equipe_executor(requisicao({"local": "vps"}, False)).status_code == 403
    assert super_equipe_executor(requisicao({"local": "vps"})).status_code == 200
    rotina.refresh_from_db()
    assert rotina.executor_consultado_em and not rotina.executor_em
    assert op.situacao_executor(rotina) == "Executor conectado"
    rotina.executor_consultado_em -= timedelta(hours=1)
    assert "Sem contato recente" in op.situacao_executor(rotina)


def test_telemetria_descarta_logs_e_nao_confunde_velha_com_recente(rotina):
    agora = timezone.now()
    dados = op.receber({"coletada_em": (agora-timedelta(hours=1)).isoformat(),
        "log": "email e CPF privados", "disco_livre_mb": 30})
    assert "log" not in dados and dados["http_5xx_15m"] is None
    assert not op.operacao_recente(dados)
    dados["coletada_em"] = agora.isoformat()
    assert op.operacao_recente(dados)
    dados["coletada_em"] = (agora+timedelta(days=1)).isoformat()
    assert not op.operacao_recente(dados)


def test_fonte_recuperada_nao_encerra_publicacao_pendente(rotina, fontes):
    fontes["robos_ia"]["estado"] = "indisponivel"
    rodar(fontes)
    item = MelhoriaSuperEquipe.objects.get()
    item.entrega, item.situacao = "012345678abc", "publicando"
    item.save()
    fontes["robos_ia"]["estado"] = "medido"
    adiantar(rotina)
    rodar(fontes)
    item.refresh_from_db()
    rotina.refresh_from_db()
    assert item.situacao == "publicando"
    assert rotina.fotografia["faltas"] == []


def test_agendamento_vencido_tambem_aparece_como_atraso(rotina):
    robo = rotina.ultimo_trabalho.robo if rotina.ultimo_trabalho else None
    from apps.agentes.models import RoboPessoal
    robo = RoboPessoal.objects.first()
    item = Execucao.objects.create(robo=robo, tipo="super_equipe", situacao="na_fila",
        nao_antes_de=timezone.now()-timedelta(hours=1))
    Execucao.objects.filter(pk=item.pk).update(criada_em=timezone.now()-timedelta(hours=2))
    assert op.coletar()["fila_atrasada"] == 1
    Execucao.objects.filter(pk=item.pk).update(nao_antes_de=timezone.now()+timedelta(hours=1))
    assert op.coletar()["fila_atrasada"] == 0


def test_desenvolvimento_reusa_resposta_paga_sem_repetir(rotina, melhoria):
    melhoria.situacao, melhoria.posse = "executando", "minha-posse"
    melhoria.ocupada_ate = timezone.now()+timedelta(minutes=15)
    melhoria.save()
    dados = {"base": "a"*40, "posse": melhoria.posse, "contexto": {"arquivos_disponiveis": []}}
    proposta = {"acao": "sem_defeito", "motivo": "Não há evidência", "beneficio": "", "ler": [], "alteracoes": []}
    resposta = SimpleNamespace(completa=True, texto=json.dumps(proposta), consumo=SimpleNamespace(pk=123, custo_estimado_usd="0.01"))
    with patch.object(dev.modelo, "conexao", return_value=SimpleNamespace(modelo_forte="gpt-6-sol")), \
         patch.object(dev.modelo, "responder", return_value=resposta) as chamada:
        assert dev.desenvolver(requisicao(dados), melhoria.pk).status_code == 200
        assert dev.desenvolver(requisicao(dados), melhoria.pk).status_code == 200
        assert chamada.call_count == 1
    # A fila não transporta o código nem o histórico de prompts.
    r = RequestFactory().get("/")
    r.admin = {"robo": True}
    assert "desenvolvimento" not in json.loads(super_equipe_fila(r).content)["melhorias"][0]


def test_resposta_desconhecida_nao_e_reenviada(rotina, melhoria):
    melhoria.situacao, melhoria.posse = "executando", "minha-posse"
    melhoria.ocupada_ate = timezone.now()+timedelta(minutes=15)
    melhoria.save()
    dados = {"base": "a"*40, "posse": melhoria.posse, "contexto": {}}
    with patch.object(dev.modelo, "conexao", return_value=SimpleNamespace(modelo_forte="gpt-6-sol")), \
         patch.object(dev.modelo, "responder", side_effect=dev.modelo.Temporario()) as chamada:
        assert dev.desenvolver(requisicao(dados), melhoria.pk).status_code == 503
        assert dev.desenvolver(requisicao(dados), melhoria.pk).status_code == 202
        assert chamada.call_count == 1
    melhoria.refresh_from_db()
    reg = next(iter(melhoria.desenvolvimento["rodadas"].values()))
    reg["iniciada_em"] = (timezone.now()-timedelta(hours=1)).isoformat()
    melhoria.save()
    assert dev.desenvolver(requisicao(dados), melhoria.pk).status_code == 409


def test_diagnostico_sem_defeito_nao_reabre_a_cada_observacao(rotina, fontes):
    fontes["robos_ia"]["estado"] = "indisponivel"
    rodar(fontes)
    item = MelhoriaSuperEquipe.objects.get()
    item.situacao = "resolvida"
    item.desenvolvimento = {"rodadas": {"a": {"resposta": {"acao": "sem_defeito"}}}}
    item.save()
    adiantar(rotina)
    rodar(fontes)
    item.refresh_from_db()
    assert item.situacao == "resolvida"
    fontes["robos_ia"]["estado"] = "medido"
    adiantar(rotina)
    rodar(fontes)
    fontes["robos_ia"]["estado"] = "indisponivel"
    adiantar(rotina)
    rodar(fontes)
    item.refresh_from_db()
    assert item.situacao == "pendente"  # uma recidiva real abre outro episódio
    assert item.desenvolvimento["historico"][0]["rodadas"]["a"]
