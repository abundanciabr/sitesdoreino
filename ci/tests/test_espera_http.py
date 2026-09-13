"""O cache só é evidência quando o servidor confirma 304 nesta consulta."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import espera
from _nucleo import ErroDeInstrumentacao


class Relogio:
    def __init__(self):
        self.agora = 0

    def __call__(self):
        return self.agora

    def dormir(self, segundos):
        self.agora += segundos


def http(status, corpo="", headers=None, exit_code=None):
    return subprocess.CompletedProcess(
        [], (0 if status == 200 else 1) if exit_code is None else exit_code,
        f"HTTP/2.0 {status}\r\n"
        + "".join(f"{k}: {v}\r\n" for k, v in (headers or {}).items())
        + "\r\n" + (json.dumps(corpo) if not isinstance(corpo, str) else corpo),
        "" if status == 200 else f"gh: HTTP {status}",
    )


def roteiro(monkeypatch, respostas):
    respostas = iter(respostas)
    chamadas = []

    def executar(args, **kwargs):
        chamadas.append((args, kwargs))
        resposta = next(respostas)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setattr(subprocess, "run", executar)
    return chamadas


def observar():
    dado = espera.chamar_gh(["gh"], "repos/dona/loja/actions/runs/9")
    return espera.Olhada(dado["status"] == "completed", dado["status"], dados=dado)


def vigiar(observador=observar, *, teto=600, intervalo=10, vozes=None):
    relogio = Relogio()
    resultado = espera.vigiar(
        observador, teto=teto, intervalo=intervalo,
        relogio=relogio, dormir=relogio.dormir,
        ao_observar=vozes.append if vozes is not None else None,
    )
    return resultado, relogio


def test_200_304_e_mudanca_revalidam_em_cada_volta(monkeypatch):
    chamadas = roteiro(monkeypatch, [
        http(200, {"status": "in_progress"}, {"ETag": 'W/"v1"'}),
        http(304),
        http(200, {"status": "completed"}, {"ETag": 'W/"v2"'}),
    ])
    vozes = []
    final, relogio = vigiar(vozes=vozes)
    assert final.pronta and relogio.agora == 20
    assert [v.olhada.resumo for v in vozes] == ["in_progress", "in_progress", "completed"]
    assert "--include" in chamadas[0][0]
    assert "If-None-Match: W/\"v1\"" in chamadas[1][0]
    assert "If-None-Match: W/\"v1\"" in chamadas[2][0]


@pytest.mark.parametrize("falha", [
    http(401), http(403, {"message": "forbidden"}), http(404), http(500), http(200, "json quebrado"),
    http(200, {"status": "completed"}, exit_code=1),
    OSError("rede indisponível"), subprocess.TimeoutExpired("gh", 1),
])
def test_erro_nunca_recicla_verde_antigo(monkeypatch, falha):
    roteiro(monkeypatch, [http(200, {"status": "completed"}, {"ETag": '"v1"'}), falha])

    def dupla():
        assert observar().pronta
        with pytest.raises(ErroDeInstrumentacao):
            observar()
        return espera.Olhada(True, "erro preservado")

    vigiar(dupla)


def test_304_sem_cache_e_erro(monkeypatch):
    roteiro(monkeypatch, [http(304)])
    with pytest.raises(ErroDeInstrumentacao, match="304.*cache"):
        observar()


def test_cache_nao_cruza_esperas(monkeypatch):
    chamadas = roteiro(monkeypatch, [http(200, {"status": "completed"}, {"ETag": '"v1"'})] * 2)
    vigiar()
    vigiar()
    assert all(not any("If-None-Match" in arg for arg in args) for args, _ in chamadas)


@pytest.mark.parametrize("mudar", ["endpoint", "gh", "token"])
def test_cache_isola_alvo_e_identidade(monkeypatch, mudar):
    chamadas = roteiro(monkeypatch, [http(200, {"status": "completed"}, {"ETag": '"v1"'})] * 2)

    def dupla():
        observar()
        if mudar == "token":
            monkeypatch.setenv("GH_TOKEN", "outra-identidade-de-teste")
        espera.chamar_gh(["outro-gh"] if mudar == "gh" else ["gh"],
                         "outro-endpoint" if mudar == "endpoint" else "repos/dona/loja/actions/runs/9")
        return espera.Olhada(True, "isolado")

    vigiar(dupla)
    assert not any("If-None-Match" in arg for arg in chamadas[1][0])


@pytest.mark.parametrize("headers,segundos", [
    ({"Retry-After": "90"}, 90),
    ({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1200"}, 200),
    ({}, 60),
])
def test_rate_limit_respeita_cooldown_e_mantem_voz(monkeypatch, headers, segundos):
    monkeypatch.setattr(espera.time, "time", lambda: 1000)
    chamadas = roteiro(monkeypatch, [
        http(429, {"message": "secondary rate limit"}, headers),
        http(200, {"status": "completed"}),
    ])
    vozes = []
    _, relogio = vigiar(vozes=vozes)
    assert relogio.agora == segundos
    assert len(chamadas) == 2
    assert all(v.erro and v.olhada is None for v in vozes[:-1])
    assert max(b.decorrido - a.decorrido for a, b in zip(vozes, vozes[1:])) <= 60


def test_secundario_repetido_dobra_espera(monkeypatch):
    roteiro(monkeypatch, [http(403, {"message": "secondary rate limit"})] * 2
            + [http(200, {"status": "completed"})])
    _, relogio = vigiar()
    assert relogio.agora == 180


def test_cooldown_maior_que_teto_nao_faz_outra_consulta(monkeypatch):
    chamadas = roteiro(monkeypatch, [http(429, {}, {"Retry-After": "300"})])
    vozes = []
    with pytest.raises(espera.TetoVencido) as erro:
        vigiar(teto=25, vozes=vozes)
    assert len(chamadas) == 1
    assert erro.value.decorrido == 25
    assert erro.value.erro is not None
    assert vozes[0].erro is not None


def test_timeout_do_transporte_usa_orcamento_restante(monkeypatch):
    chamadas = roteiro(monkeypatch, [http(200, {"status": "completed"})])
    vigiar(teto=7)
    assert 0 < chamadas[0][1]["timeout"] <= 7


def test_poll_interval_e_respeitado(monkeypatch):
    roteiro(monkeypatch, [http(200, {"status": "in_progress"}, {"X-Poll-Interval": "45"}),
                         http(200, {"status": "completed"})])
    _, relogio = vigiar()
    assert relogio.agora == 45


def test_304_sem_poll_interval_preserva_cadencia_recebida(monkeypatch):
    roteiro(monkeypatch, [http(200, {"status": "in_progress"},
                              {"X-Poll-Interval": "45", "ETag": '"v1"'}),
                         http(304), http(200, {"status": "completed"})])
    _, relogio = vigiar()
    assert relogio.agora == 90


def test_ultima_cota_valida_aguarda_reset_antes_de_consultar(monkeypatch):
    monkeypatch.setattr(espera.time, "time", lambda: 1000)
    roteiro(monkeypatch, [http(200, {"status": "in_progress"},
                              {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1200"}),
                         http(200, {"status": "completed"})])
    _, relogio = vigiar()
    assert relogio.agora == 200


def test_200_sem_etag_descarta_validador_antigo(monkeypatch):
    chamadas = roteiro(monkeypatch, [http(200, {"status": "in_progress"}, {"ETag": '"v1"'}),
                                    http(200, {"status": "in_progress"}),
                                    http(200, {"status": "completed"})])
    vigiar()
    assert not any("If-None-Match" in a for a in chamadas[-1][0])


def test_json_invalido_nao_vira_cache_para_304(monkeypatch):
    roteiro(monkeypatch, [http(200, "{", {"ETag": '"v1"'}), http(304)])

    def dupla():
        with pytest.raises(ErroDeInstrumentacao, match="JSON"):
            observar()
        with pytest.raises(ErroDeInstrumentacao, match="304.*cache"):
            observar()
        return espera.Olhada(True, "sem cache")

    vigiar(dupla)


def test_cada_endpoint_recebe_so_o_tempo_restante(monkeypatch):
    relogio = Relogio()
    roteiro(monkeypatch, [http(200, {"status": "completed"})])

    def dupla():
        observar()
        relogio.agora = 10
        with pytest.raises(ErroDeInstrumentacao, match="teto"):
            espera.chamar_gh(["gh"], "segundo-endpoint")
        return espera.Olhada(True, "terminou tarde")

    with pytest.raises(espera.TetoVencido):
        espera.vigiar(dupla, teto=10, intervalo=1, relogio=relogio, dormir=relogio.dormir)


def test_cota_final_valida_nao_e_transformada_em_erro(monkeypatch):
    roteiro(monkeypatch, [http(200, {"status": "completed"}, {"X-RateLimit-Remaining": "0"})])
    final, relogio = vigiar()
    assert final.pronta and relogio.agora == 0


@pytest.mark.parametrize("valor", ["nan", "inf", "-20", "invalido"])
def test_retry_after_invalido_usa_um_minuto(monkeypatch, valor):
    roteiro(monkeypatch, [http(429, {}, {"Retry-After": valor}), http(200, {"status": "completed"})])
    _, relogio = vigiar()
    assert relogio.agora == 60


def test_troca_de_conta_no_windows_invalida_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    configuracao = tmp_path / "GitHub CLI" / "hosts.yml"
    configuracao.parent.mkdir()
    configuracao.write_text("usuario: antes")
    chamadas = roteiro(monkeypatch, [http(200, {"status": "completed"}, {"ETag": '"v1"'})] * 2)

    def dupla():
        observar()
        configuracao.write_text("usuario: outra conta")
        observar()
        return espera.Olhada(True, "outra conta")

    vigiar(dupla)
    assert not any("If-None-Match" in a for a in chamadas[-1][0])


def test_configuracao_inacessivel_e_erro_de_instrumentacao(monkeypatch):
    def inacessivel(*args, **kwargs):
        raise PermissionError("configuração bloqueada")

    monkeypatch.setattr(Path, "stat", inacessivel)
    with pytest.raises(ErroDeInstrumentacao, match="conta.*gh"):
        observar()


@pytest.mark.parametrize("alvo", ["run", "deploy", "portao"])
def test_observadores_revalidam_304_e_preservam_vermelho(monkeypatch, alvo):
    import esperar
    import portao_de_deploy

    workflow = ".github/workflows/deploy-celula.yml"
    pendente = dict(id=9, path=workflow, event="push", status="in_progress", conclusion=None)
    final = dict(pendente, status="completed", conclusion="failure")
    corpo = lambda run: run if alvo == "run" else {"workflow_runs": [run]}
    chamadas = roteiro(monkeypatch, [http(200, corpo(pendente), {"ETag": '"v1"'}),
                                    http(304), http(200, corpo(final))])
    if alvo == "portao":
        relogio = Relogio()
        motor = espera.vigiar
        monkeypatch.setattr(portao_de_deploy, "vigiar", lambda observar, **kw: motor(
            observar, **kw, relogio=relogio, dormir=relogio.dormir,
        ))
        ctx = portao_de_deploy.Contexto("dona/loja", "a" * 40, "99", "push", [], "celula",
                                       ["gh"], 10, 100, 600)
        escolhidos, _ = portao_de_deploy.esperar_workflows(ctx, ctx.sha, {workflow: ()}, "push")
        assert escolhidos[workflow]["conclusion"] == "failure"
    else:
        observador = esperar.observar_run if alvo == "run" else esperar.observar_deploy
        resultado, _ = vigiar(lambda: observador(["gh"], "dona/loja", "9" if alvo == "run" else "a" * 40))
        assert resultado.dados["verde"] is False
    assert len(chamadas) == 3
    assert "If-None-Match: \"v1\"" in chamadas[1][0]
