"""A conferência lê grafos por projeto e mantém as falhas reais."""
from entregas_migracoes import _migracoes, _problemas


def grafo(monkeypatch, arquivos):
    def git(repo, *args):
        if args[0] == "ls-tree":
            return "\n".join(arquivos)
        return arquivos[args[1].split(":", 1)[1]]
    monkeypatch.setattr("entregas_migracoes._git", git)
    return _migracoes("sem-rede", "candidata")


def migracao(*deps):
    return "class Migration:\n    dependencies = %r\n" % list(deps)


def test_servicos_com_core_independentes_nao_disputam_pontas(monkeypatch):
    arquivos = {
        "services/admin/apps/core/migrations/0001_initial.py": migracao(),
        "services/admin/apps/core/migrations/0049_perfil.py": migracao(("core", "0001_initial")),
        "services/leads/apps/core/migrations/0001_initial.py": migracao(),
        "services/leads/apps/core/migrations/0008_captura.py": migracao(("core", "0001_initial")),
    }
    resultado = grafo(monkeypatch, arquivos)
    assert len(resultado) == 4
    assert _problemas(resultado) == set()


def test_duas_pontas_no_mesmo_servico_continuam_recusadas(monkeypatch):
    arquivos = {
        "services/admin/apps/core/migrations/0001_initial.py": migracao(),
        "services/admin/apps/core/migrations/0002_a.py": migracao(("core", "0001_initial")),
        "services/admin/apps/core/migrations/0002_b.py": migracao(("core", "0001_initial")),
    }
    assert any("pontas concorrentes" in p for p in _problemas(grafo(monkeypatch, arquivos)))


def test_dependencia_nao_e_satisfeita_por_outro_servico(monkeypatch):
    arquivos = {
        "services/admin/apps/core/migrations/0001_initial.py": migracao(),
        "services/admin/apps/core/migrations/0003_nova.py": migracao(("core", "0002_outra")),
        "services/leads/apps/core/migrations/0002_outra.py": migracao(),
    }
    assert any("dependência ausente" in p for p in _problemas(grafo(monkeypatch, arquivos)))


def test_dependencia_entre_apps_do_mesmo_projeto_e_resolvida(monkeypatch):
    arquivos = {
        "services/admin/apps/core/migrations/0001_initial.py": migracao(),
        "services/admin/apps/gestao/migrations/0001_initial.py": migracao(("core", "0001_initial")),
    }
    assert _problemas(grafo(monkeypatch, arquivos)) == set()


def test_ciclo_do_mesmo_servico_continua_recusado(monkeypatch):
    arquivos = {
        "services/admin/apps/core/migrations/0001_a.py": migracao(("core", "0002_b")),
        "services/admin/apps/core/migrations/0002_b.py": migracao(("core", "0001_a")),
    }
    assert any("ciclo de migrações" in p for p in _problemas(grafo(monkeypatch, arquivos)))


def test_dependencia_dinamica_continua_recusada_sem_executar(monkeypatch):
    arquivos = {
        "services/admin/apps/core/migrations/0001_initial.py": "raise RuntimeError('nunca executar')\nclass Migration:\n    dependencies = calcular()\n",
    }
    assert any("dependência dinâmica" in p for p in _problemas(grafo(monkeypatch, arquivos)))
