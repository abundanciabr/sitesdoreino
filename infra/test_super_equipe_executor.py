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
