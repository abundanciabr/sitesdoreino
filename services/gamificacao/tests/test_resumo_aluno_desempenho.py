"""Medição isolada: quatro GETs antigos contra resumo individual.

Rode com ``ci/testar_celula.py gamificacao tests/test_resumo_aluno_desempenho.py -s``.
Os tempos incluem o Django test client e PostgreSQL de teste; não são tempos
de navegação nem de produção. Nenhuma asserção depende da latência.
"""

import json
from statistics import median
from time import perf_counter_ns

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.gamificacao.models import PerfilJogador, Pessoa


SITE = "benchmark-resumo-isolado"
PESSOA = "aluno-sintetico-0000"
TOKEN = "token-sintetico-admin"
BASE = "/api/gamificacao"


def _amostra(client, *, novo):
    caminhos = (
        [f"{BASE}/resumo-aluno/{SITE}/{PESSOA}"] if novo else [
            f"{BASE}/jornada-sandbox/{SITE}/{PESSOA}",
            f"{BASE}/quadro",
            f"{BASE}/economia/conquistas",
            f"{BASE}/faixa-do-aluno?pessoa_id={PESSOA}",
        ]
    )
    with CaptureQueriesContext(connection) as consultas:
        inicio = perf_counter_ns()
        respostas = [client.get(caminho, HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
                    for caminho in caminhos]
        milissegundos = (perf_counter_ns() - inicio) / 1_000_000
    assert all(resposta.status_code == 200 for resposta in respostas), [
        (caminho, resposta.status_code, resposta.content[:150])
        for caminho, resposta in zip(caminhos, respostas)
    ]
    corpos = [resposta.json() for resposta in respostas]
    return {
        "ms": milissegundos,
        "sql": len(consultas),
        "bytes_json": sum(len(resposta.content) for resposta in respostas),
        "corpos": corpos,
    }


@pytest.mark.django_db
def test_resumo_individual_custo_contra_quatro_gets_reais(client, monkeypatch, settings):
    settings.TOKENS_ACEITOS = {TOKEN}
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", TOKEN)
    monkeypatch.setenv("SITE_ID", SITE)

    anterior = 0
    for total in (1, 100, 1000):
        pessoas = [Pessoa(id_da_plataforma=f"aluno-sintetico-{i:04d}",
                          email=f"aluno-{i:04d}@example.invalid")
                   for i in range(anterior, total)]
        Pessoa.objects.bulk_create(pessoas, batch_size=500)
        PerfilJogador.objects.bulk_create([
            PerfilJogador(pessoa_id=pessoa.id_da_plataforma, site_id=SITE,
                          xp_total=i * 10, nivel=1)
            for i, pessoa in enumerate(pessoas, start=anterior)
        ], batch_size=500)
        anterior = total

        # Aquecimento simétrico; medir 7 vezes cada e alternar a ordem.
        _amostra(client, novo=False)
        _amostra(client, novo=True)
        antigas, novas = [], []
        for repeticao in range(7):
            primeira, segunda = (False, True) if repeticao % 2 == 0 else (True, False)
            resultados = {primeira: _amostra(client, novo=primeira),
                          segunda: _amostra(client, novo=segunda)}
            antigas.append(resultados[False])
            novas.append(resultados[True])

        antigo, novo = antigas[0]["corpos"], novas[0]["corpos"][0]
        quadro = antigo[1]
        individuo = next(linha for linha in quadro if linha["pessoa_id"] == PESSOA)
        assert len(quadro) == total
        assert novo["perfil"]["xp"] == individuo["xp"]
        assert novo["perfil"]["nivel"] == individuo["nivel"]
        assert novo["faixa"]["atual"]["ordem"] == antigo[3]["atual"]["ordem"]
        assert len(novo["sandbox"]["avaliacoes"]) == len(antigo[0]["avaliacoes"])

        resultado = {
            "cenario": "PostgreSQL e Django test client isolados",
            "perfis_no_site": total,
            "amostras_por_forma": 7,
            "antigo": {
                "get_http": 4,
                "linhas_quadro": len(quadro),
                "sql": median(a["sql"] for a in antigas),
                "bytes_json": median(a["bytes_json"] for a in antigas),
                "mediana_ms": round(median(a["ms"] for a in antigas), 3),
            },
            "novo": {
                "get_http": 1,
                "perfis_na_resposta": int(novo["perfil"] is not None),
                "sql": median(a["sql"] for a in novas),
                "bytes_json": median(a["bytes_json"] for a in novas),
                "mediana_ms": round(median(a["ms"] for a in novas), 3),
            },
        }
        print("RESUMO_ALUNO_BENCHMARK " + json.dumps(resultado, ensure_ascii=False))
