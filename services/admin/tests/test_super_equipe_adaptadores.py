import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.agentes import super_equipe as equipe
from apps.agentes.models import Consumo, Execucao, RotinaSuperEquipe
from apps.agentes.super_equipe_operacao import receber, guardar_operacao, servidor


@pytest.mark.django_db
def test_contrato_instalado_e_amostra_isolam_site_e_conteudo():
    e = Execucao.objects.create(tipo="super_equipe", pedido="SEGREDO_DO_PEDIDO",
        chave_de_repeticao="CHAVE_PRIVADA", estado={"site_id": "ensaio",
        "resultados": {"jez_humble": {"texto": "RESPOSTA_PRIVADA"}},
        "versoes_perfil": {"jez_humble": "1"}})
    outro = Execucao.objects.create(tipo="super_equipe", estado={"site_id": "outro"})
    dados = equipe._contratos_tecnicos("ensaio")
    assert dados["contratos"]["execucao"]["chave_unica"] is True
    assert dados["contratos"]["ferramenta"]["unicidade"] == [["execucao", "call_id"]]
    assert [i["id"] for i in dados["itens"]] == [e.pk]
    assert dados["itens"][0]["respostas_salvas"] == 1
    texto = json.dumps(dados)
    assert all(s not in texto for s in ("SEGREDO_DO_PEDIDO", "CHAVE_PRIVADA", "RESPOSTA_PRIVADA"))


@pytest.mark.django_db
def test_ia_separa_reserva_sem_consulta_ou_reenvio():
    e = Execucao.objects.create(tipo="super_equipe", estado={"site_id": "ensaio"})
    Consumo.objects.create(execucao=e, modelo="ensaio", custo_estimado_usd=Decimal("0.01"))
    incerto = Consumo.objects.create(execucao=e, modelo="ensaio", resposta_id="IDENTIFICADOR_PRIVADO",
        custo_estimado_usd=Decimal("0.228772"), desconhecido=True)
    outro = Execucao.objects.create(tipo="super_equipe", estado={"site_id": "outro"})
    Consumo.objects.create(execucao=outro, modelo="ensaio", custo_estimado_usd=Decimal("2"))
    with patch.object(equipe.modelo, "conexao", return_value=SimpleNamespace(modelo_forte="ensaio")), \
         patch.object(equipe.modelo, "autorizacao_ativa", return_value=None), \
         patch.object(equipe.modelo, "responder") as pago:
        dados = equipe._robos_ia("ensaio")
    assert not pago.called
    assert dados["uso_com_resposta_registrada_usd"] == Decimal("0.01")
    assert dados["reserva_incerta_usd"] == Decimal("0.228772")
    assert dados["custo_tecnico_registrado_usd"] == Decimal("0.238772")
    assert dados["chamadas_incertas"] == 1
    assert "IDENTIFICADOR_PRIVADO" not in str(dados)
    incerto.refresh_from_db()
    assert incerto.desconhecido and incerto.custo_estimado_usd == Decimal("0.228772")


@pytest.mark.django_db
def test_serie_nao_regrede_nao_soma_janelas_e_preserva_pausa():
    rotina = RotinaSuperEquipe.objects.create(host="meshcraft.top", ativa=False)
    agora = timezone.now()
    for n in range(35):
        nova = receber({"coletada_em": (agora+timedelta(minutes=n)).isoformat(),
            "disco_livre_mb": 100-n, "http_5xx_15m": None, "log": "SEGREDO"})
        guardar_operacao(rotina, {"operacao": nova})
    rotina.refresh_from_db()
    assert len(rotina.operacao["serie"]) == 30
    assert rotina.operacao["serie"][-1]["disco_livre_mb"] == 66
    assert rotina.operacao["serie"][-1]["http_5xx_15m"] is None
    assert not rotina.ativa and "SEGREDO" not in json.dumps(rotina.operacao)
    assert guardar_operacao(rotina, {"operacao": receber({"coletada_em": agora.isoformat()})}) is None
    rotina.refresh_from_db()
    assert rotina.operacao["disco_livre_mb"] == 66
    with patch("apps.agentes.super_equipe_operacao.timezone.now", return_value=agora+timedelta(minutes=40)):
        assert servidor()["estado"] == "indisponivel"
    posterior = receber({"coletada_em": (agora+timedelta(hours=2)).isoformat()})
    guardar_operacao(rotina, {"operacao": posterior})
    rotina.refresh_from_db()
    assert len(rotina.operacao["serie"]) == 1 and rotina.operacao["disco_livre_mb"] is None
