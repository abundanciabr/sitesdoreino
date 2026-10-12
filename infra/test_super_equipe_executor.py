from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


def carregar(nome):
    spec = importlib.util.spec_from_file_location(nome, Path(__file__).with_name(nome+".py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


ex = carregar("super_equipe_executor")
co = carregar("super_equipe_coletor")


@pytest.mark.parametrize("caminho", ["services/checkout/apps/core/views.py", "services/aplicacao/executor.py",
    "services/pagamentos/apps/core/views.py", "packages/site_errors/a.py", "services/admin/apps/core/documentos.py",
    "services/admin/apps/agentes/super_equipe.py", "services/admin/apps/core/../../settings.py", "infra/publicar.py", None])
def test_nao_edita_areas_reservadas(caminho):
    assert not ex.permitido(caminho)


def test_coleta_sem_log_pessoal_e_sem_zero_inventado():
    assert co.contar(["nenhum acesso medido"])["http_5xx_15m"] is None
    assert co.contar(['INFO: 10.0.0.1 GET /?cpf=privado HTTP/1.1" 500 Internal Server Error',
                      'GET / HTTP/1.1" 404 Not Found', 'GET / HTTP/1.1" 200 OK']) == {
                          "http_5xx_15m": 1, "http_404_15m": 1}


def test_edicao_preserva_texto_inclusive_fim_do_arquivo(monkeypatch):
    texto = "\nVALOR = 1\n\n"
    chamadas = []
    def git(*args, entrada=None, literal=False):
        chamadas.append((args, entrada))
        return {"ls-tree": "100644 blob abc\tservices/admin/apps/core/medicao.py", "show": texto,
                "hash-object": "blob", "write-tree": "arvore", "commit-tree": "commit"}.get(args[0], "")
    monkeypatch.setattr(ex, "git", git)
    assert ex.montar_commit("a"*40, [{"caminho": "services/admin/apps/core/medicao.py", "antes": "VALOR = 1", "depois": "VALOR = 2"}]) == "commit"
    assert next(entrada for args, entrada in chamadas if args[0] == "hash-object") == "\nVALOR = 2\n\n"


def test_ativacao_sem_leitura_nova_nao_encerra(monkeypatch):
    monkeypatch.setattr(ex, "publicar", lambda a: {"candidata": "abc", "operacao": {"fase": "ativa", "ativadas": ["aplicacao"], "candidata": "abc"}})
    monkeypatch.setattr(ex, "salvar", lambda a: None)
    monkeypatch.setattr(ex, "api", lambda a: {"observacao": {}})
    resultado = Mock()
    monkeypatch.setattr(ex, "resultado", resultado)
    ex.confirmar_entrega({"id": 1, "entrega": "012345678abc"})
    assert resultado.call_args.args[1] == "publicando"


@pytest.mark.parametrize("fase", ["ativa", "preservada em versão posterior"])
def test_so_encerra_achado_apos_ativacao_e_nova_leitura(monkeypatch, fase):
    monkeypatch.setattr(ex, "publicar", lambda a: {"candidata": "abc", "operacao": {"fase": fase, "ativadas": ["aplicacao"], "candidata": "abc"}})
    monkeypatch.setattr(ex, "api", lambda a: {"observacao": {"consultado_em": datetime.now(timezone.utc).isoformat(),
        "faltas": [], "paginas_publicas": {"itens": [{"estado": "medido", "http": 200}]}}})
    resultado = Mock()
    monkeypatch.setattr(ex, "resultado", resultado)
    ex.confirmar_entrega({"id": 1, "entrega": "012345678abc", "evidencia": {"achado": "falha"},
                         "ativacao_conferida_em": (datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()})
    assert resultado.call_args.args[1] == "resolvida"


def test_fotografia_antiga_nao_resolve_ocorrencia_nova():
    item = {"evidencia": {"operacao": "fonte", "achado": "falha", "consultado_em": "2026-10-11T11:00:00Z"}}
    assert not ex.fonte_recuperada(item, {"faltas": [], "consultado_em": "2026-10-11T10:00:00Z"})
    assert ex.fonte_recuperada(item, {"faltas": [], "consultado_em": "2026-10-11T12:00:00Z"})
    assert not ex.fonte_recuperada(item, {"faltas": ["falha"], "consultado_em": "2026-10-11T12:00:00Z"})


def test_publicacao_sem_medicao_do_efeito_permanece_aberta(monkeypatch):
    monkeypatch.setattr(ex, "publicar", lambda _: {"candidata": "abc", "operacao": {
        "fase": "ativa", "ativadas": ["aplicacao"], "candidata": "abc"}})
    monkeypatch.setattr(ex, "api", lambda _: {"observacao": {
        "consultado_em": datetime.now(timezone.utc).isoformat(),
        "paginas_publicas": {"itens": [{"estado": "medido", "http": 200}]}}})
    resultado = Mock()
    monkeypatch.setattr(ex, "resultado", resultado)
    ex.confirmar_entrega({"id": 1, "entrega": "012345678abc", "evidencia": {},
        "ativacao_conferida_em": (datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()})
    assert resultado.call_args.args[1] == "publicando"


def test_coletor_mede_repeticao_sem_varrer_objetos(tmp_path):
    import json
    from types import SimpleNamespace
    pasta = tmp_path/'entregas'
    pasta.mkdir()
    reg = {"id": "a"*12, "estado": "conflito", "tentativas": 8,
           "commit": "b"*40, "base": "c"*40, "main_observada": "d"*40}
    (pasta/(reg["id"]+'.json')).write_text(json.dumps(reg))
    d = SimpleNamespace(total=1000000000, used=600000000, free=400000000)
    a = co.armazenamento(1000, d, {}, pasta)
    assert a['integrador']['repeticoes_identicas'] is None
    reg['tentativas'] += 2
    (pasta/(reg["id"]+'.json')).write_text(json.dumps(reg))
    d.used += 1048576
    d.free -= 1048576
    b = co.armazenamento(1060, d, a, pasta)
    assert b['integrador']['repeticoes_identicas'] == 2
    assert b['crescimento_mb_h'] == 60 and b['pico_entre_coletas_mb'] == 1
    reg['main_observada'] = 'e'*40
    reg['tentativas'] += 1
    (pasta/(reg["id"]+'.json')).write_text(json.dumps(reg))
    assert co.armazenamento(1120, d, b, pasta)['integrador']['repeticoes_identicas'] == 0
