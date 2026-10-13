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
from apps.agentes.super_equipe_entregas import registrar
from apps.agentes.super_equipe_perfis import contexto_do_perfil
from tests.test_super_equipe_entregas import prova


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


@pytest.mark.django_db
def test_capacidade_e_sondas_minimizadas_na_serie_do_perfil():
    r = RotinaSuperEquipe.objects.create(host='meshcraft.top', ativa=True)
    agora = timezone.now()
    for n in range(2):
        dados = receber({'coletada_em': (agora+timedelta(seconds=60*n)).isoformat(),
            'cpu_ocupada_percentual': None if n == 0 else 0,
            'memoria_usada_mb': 250, 'io_escrita_bytes_s': None if n == 0 else 1024,
            'sondas_http': [{'alvo': 'inicio', 'http': 200, 'tempo_ms': 42, 'corpo': 'SEGREDO'}],
            '_capacidade_contadores': {'segredo': 'DESCARTAR'}})
        guardar_operacao(r, {'operacao': dados})
    atual = servidor()
    assert atual['serie'][0]['cpu_ocupada_percentual'] is None
    assert atual['serie'][1]['cpu_ocupada_percentual'] == 0
    assert atual['serie'][1]['sondas_http'][0]['tempo_ms'] == 42
    assert all(x not in json.dumps(atual) for x in ('SEGREDO', 'DESCARTAR', '_capacidade_contadores'))
    assert contexto_do_perfil('liz_fong_jones', 'Leia', {'servidor': atual}, {})['fontes']['servidor']['serie'] == atual['serie']


@pytest.mark.parametrize('campos', [ {'cpu_ocupada_percentual': 101},
    {'io_leitura_bytes_s': float('nan')}, {'memoria_usada_mb': -1},
    {'sondas_http': [{'alvo': 'externo', 'http': 200}]} ])
def test_capacidade_rejeita_valor_invalido_e_alvo_arbitrario(campos):
    with pytest.raises(ValueError):
        receber({'coletada_em': timezone.now().isoformat(), **campos})


@pytest.mark.django_db
def test_nicole_recebe_tempos_importados_sem_somar_etapas_ou_excluir_incompleta():
    r = RotinaSuperEquipe.objects.create(host='meshcraft.top', site_id='ensaio')
    inicio = timezone.now()-timedelta(minutes=10)
    dados = prova()
    dados['recebida_em'] = inicio.isoformat()
    dados['operacao'].update(iniciada_em=(inicio+timedelta(seconds=10)).isoformat(),
        concluida_em=(inicio+timedelta(seconds=40)).isoformat(),
        tempos_segundos={'ensaio_aplicacao': 30, 'ativacao_aplicacao': 5, 'segredo': 999})
    registrar(r.host, dados)
    incompleta = prova()
    incompleta['id'] = incompleta['operacao']['evidencia_publicador']['id'] = '1'*12
    registrar(r.host, incompleta)
    fluxo = equipe._fluxo_entregas('ensaio')['entregas_codigo']
    assert fluxo['amostra'] == 2
    a = next(i for i in fluxo['itens'] if i['id'] == 'a'*12)
    b = next(i for i in fluxo['itens'] if i['id'] == '1'*12)
    assert a['espera_recebimento_inicio_segundos'] == 10
    assert a['duracao_recebimento_conclusao_segundos'] == 40
    assert a['tempos_segundos']['ensaio_aplicacao'] == 30
    assert b['duracao_recebimento_conclusao_segundos'] is None
    assert 'segredo' not in json.dumps(fluxo)
    assert contexto_do_perfil('nicole_forsgren', 'Leia', {'fluxo_entregas': fluxo}, {})['fontes']['fluxo_entregas']['amostra'] == 2
