import pytest

from apps.core.acesso_site import e_administrador
from apps.core.models import Administrador

pytestmark = pytest.mark.django_db


def test_acesso_usa_lista_vigente_e_desativacao_imediata(settings):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    admin = Administrador.objects.create(email="promovido@exemplo.com")
    assert e_administrador(" DONO@EXEMPLO.COM ")
    assert e_administrador(admin.email)
    assert not e_administrador("aluno@exemplo.com")
    assert not e_administrador("")
    admin.ativo = False
    admin.save()
    assert not e_administrador(admin.email)
    assert e_administrador("dono@exemplo.com")
