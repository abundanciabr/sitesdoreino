import pytest

from apps.core import participacao
from apps.cursos.models import ComentarioDeAula, Pessoa
from tests.conftest import ANA, BETO


@pytest.mark.django_db
def test_avaliacao_restringe_comentario_publico_e_devolve_sem_acao_manual(aula_publicada, monkeypatch):
    ana = Pessoa.objects.create(id_da_plataforma=ANA["id"], nome_exibido="Ana")
    beto = Pessoa.objects.create(id_da_plataforma=BETO["id"], nome_exibido="Beto")
    comentario = ComentarioDeAula.objects.create(aula=aula_publicada, autor=beto, corpo="Uma dúvida", publico=True)
    estado = {"segmento": "detrator"}
    monkeypatch.setattr(participacao, "consultar", lambda ids: {str(beto.pk): estado})
    consulta = ComentarioDeAula.objects.filter(pk=comentario.pk)
    assert not participacao.comentarios_visiveis(consulta, ana).exists()
    assert participacao.comentarios_visiveis(consulta, beto).exists()
    estado["segmento"] = "promotor"
    assert participacao.comentarios_visiveis(consulta, ana).exists()
    comentario.refresh_from_db()
    assert comentario.publico
