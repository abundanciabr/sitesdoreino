"""Por padrão os testes entram como administrador (a página é só de admin).

`test_acesso_so_admin.py` desliga isto e testa o guard de verdade.
"""

import pytest


@pytest.fixture(autouse=True)
def _admin_por_padrao(request, monkeypatch):
    if request.module.__name__.endswith("test_acesso_so_admin"):
        return
    monkeypatch.setattr("apps.core.acesso.e_admin", lambda req, pessoa_id: True)
    monkeypatch.setattr("apps.core.views.e_admin", lambda req, pessoa_id: True)
