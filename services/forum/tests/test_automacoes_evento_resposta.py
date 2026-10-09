"""A carta de resposta vai a quem abriu o tópico, sem texto de alunos."""
from types import SimpleNamespace

from apps.forum import eventos
from apps.forum.models import Area, Topico


def _mensagem(*, autor_topico="pessoa-1", ator="pessoa-2", estado="publicado",
              area_ativa=True):
    area = SimpleNamespace(pk=8, ativa=area_ativa, curso_id="",
                           visibilidade=Area.Visibilidade.PUBLICA)
    topico = SimpleNamespace(pk=12, autor=SimpleNamespace(id_da_plataforma=autor_topico),
                             estado=estado, area=area, area_id=8)
    mensagem = SimpleNamespace(pk=42, topico=topico, topico_id=12, removida_em=None,
                               texto="conteúdo privado")
    return mensagem, ator


def test_resposta_envia_evento_ao_autor_do_topico_sem_copiar_texto(monkeypatch):
    emitidos = []
    monkeypatch.setattr(eventos, "emitir", lambda nome, dados, **kw: emitidos.append((nome, dados, kw)))
    monkeypatch.setattr("apps.core.menu.site_id_do_host", lambda host: "s1")
    mensagem, ator = _mensagem()
    eventos.mensagem_criada(site_id="s1", mensagem=mensagem, ator_id=ator, host="meshcraft.top")
    assert [nome for nome, _, _ in emitidos] == ["forum.mensagem-criada", "forum.resposta-criada"]
    assert emitidos[1][1] == {
        "site_id": "s1", "topico_id": "12", "mensagem_id": "42",
        "area_id": "8", "destinatario_id": "pessoa-1",
        "link": "https://meshcraft.top/forum/t/12#m42",
    }
    assert "conteúdo privado" not in str(emitidos)


def test_autor_proprio_ou_topico_invisivel_nao_cria_aviso(monkeypatch):
    emitidos = []
    monkeypatch.setattr(eventos, "emitir", lambda nome, dados, **kw: emitidos.append(nome))
    monkeypatch.setattr("apps.core.menu.site_id_do_host", lambda host: "s1")
    for mensagem, ator in (
        _mensagem(ator="pessoa-1"),
        _mensagem(estado=Topico.Estado.ESPERANDO),
        _mensagem(area_ativa=False),
    ):
        eventos.mensagem_criada(site_id="s1", mensagem=mensagem, ator_id=ator,
                                 host="meshcraft.top")
    assert emitidos == ["forum.mensagem-criada"] * 3


def test_host_de_outro_site_nao_vira_link_para_o_destinatario(monkeypatch):
    emitidos = []
    monkeypatch.setattr(eventos, "emitir", lambda nome, dados, **kw: emitidos.append(nome))
    monkeypatch.setattr("apps.core.menu.site_id_do_host", lambda host: "outro-site")
    mensagem, ator = _mensagem()
    eventos.mensagem_criada(site_id="s1", mensagem=mensagem, ator_id=ator,
                             host="outro.exemplo")
    assert emitidos == ["forum.mensagem-criada"]


def test_destinatario_sem_acesso_atual_nao_recebe_aviso(monkeypatch):
    emitidos = []
    monkeypatch.setattr(eventos, "emitir", lambda nome, dados, **kw: emitidos.append(nome))
    monkeypatch.setattr("apps.core.menu.site_id_do_host", lambda host: "s1")
    monkeypatch.setattr(eventos, "_destinatario_pode_ler", lambda area, pessoa: False)
    mensagem, ator = _mensagem()
    eventos.mensagem_criada(site_id="s1", mensagem=mensagem, ator_id=ator,
                             host="meshcraft.top")
    assert emitidos == ["forum.mensagem-criada"]
