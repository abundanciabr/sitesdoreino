"""Guardas das FERRAMENTAS DO ADMINISTRADOR — editar, tirar do ar, deixar privado.

Mandato do mantenedor em 30/08/2026: *"Crie as opções (que devem aparecer
apenas para o Admin) de editar, deletar, deixar privado, e etc; tudo no fórum."*

As quatro coisas que esta suíte existe para travar:

1. **Ninguém além do administrador enxerga ou alcança as ferramentas.** Nem
   aluno, nem professor, nem visitante — e a recusa é 404, nunca 403, porque um
   403 confirmaria que a porta existe.
2. **Nada é apagado de verdade.** Toda ação de "deletar" tem, do outro lado, uma
   contagem no banco que não mudou. Se um dia alguém trocar o `update` por um
   `delete()`, é aqui que o vermelho aparece.
3. **A tela e a porta concordam.** O botão aparece exatamente quando a view
   aceita, porque as duas perguntam a mesma função (`pode_moderar`).
4. **O formulário funciona de verdade**, com CSRF ligado, do jeito que o
   navegador do mantenedor vai usar (`armadilhas/204`).

**Todo teste daqui atravessa a porta pela rede, não pela função** — a mesma
regra de `test_escrever.py`. Um `Ator` montado à mão prova o que eu acredito,
não o que o site faz.
"""

from __future__ import annotations

import re

import httpx
import pytest
from django.contrib.postgres.search import SearchQuery
from django.test import Client
from django.urls import reverse

from apps.forum.models import Area, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db

COOKIE = "meshcraft_sessao=um-cookie-opaco-qualquer"
FERRAMENTAS = "Ferramentas do administrador"

SESSAO_DO_DONO = {
    "autenticado": True,
    "id": "p_dono",
    "email": "dono@exemplo.com",
    "nome_exibido": "Davi",
}
SESSAO_DA_ANA = {
    "autenticado": True,
    "id": "p_ana",
    "email": "ana@exemplo.com",
    "nome_exibido": "Ana",
}
SESSAO_DO_PROFESSOR = {
    "autenticado": True,
    "id": "p_prof",
    "email": "prof@exemplo.com",
    "nome_exibido": "Professor",
}


@pytest.fixture
def env(monkeypatch):
    """O env mínimo, com as DUAS listas de poder preenchidas.

    `ADMIN_EMAILS` com uma pessoa e `FORUM_PROFESSORES` com outra: é o que
    permite provar que o professor não herda as ferramentas do administrador,
    que foi a decisão de 30/08/2026 e não um esquecimento.
    """
    for nome, valor in [
        ("IDENTIDADE_API_URL", "http://identidade:8000/interno"),
        ("IDENTIDADE_API_TOKEN", "tok-id"),
        ("ALUNOS_API_URL", "http://alunos:8000/api/alunos"),
        ("ALUNOS_API_TOKEN", "tok-al"),
        ("FORUM_PROFESSORES", "prof@exemplo.com"),
        ("ADMIN_EMAILS", "dono@exemplo.com"),
    ]:
        monkeypatch.setenv(nome, valor)


def dublar(monkeypatch, *, sessao=None, categoria=None):
    """A rede das duas células vizinhas, dublada por URL."""

    def falso_get(self, url, **kwargs):
        endereco = str(url)
        if "identidade" in endereco:
            if sessao is None:
                raise AssertionError(f"chamada inesperada à identidade: {endereco}")
            return httpx.Response(200, json=sessao)
        if categoria is None:
            raise AssertionError(f"chamada inesperada à alunos: {endereco}")
        return httpx.Response(200, json={"categoria": categoria})

    monkeypatch.setattr(httpx.Client, "get", falso_get)


def como_dono(monkeypatch):
    """O administrador, e de propósito SEM matrícula.

    O poder dele não pode vir de ser aluno: se um dia `pode_moderar` passar a
    depender de `eh_aluno` por acidente, esta escolha é o que deixa a suíte
    vermelha.
    """
    dublar(monkeypatch, sessao=SESSAO_DO_DONO, categoria="cadastrado")


def como_aluna(monkeypatch):
    dublar(monkeypatch, sessao=SESSAO_DA_ANA, categoria="aluno")


def como_professor(monkeypatch):
    dublar(monkeypatch, sessao=SESSAO_DO_PROFESSOR, categoria="cadastrado")


def sem_login(monkeypatch):
    dublar(monkeypatch, sessao={"autenticado": False})


@pytest.fixture
def sala():
    """A área de aluno: trancada para o mundo, aberta para a turma."""
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas gerais",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.ALUNO,
    )


@pytest.fixture
def avisos():
    """A única forma legal de área pública: quem publica é a escola."""
    return Area.objects.create(
        slug="avisos",
        nome="Avisos da escola",
        visibilidade=Area.Visibilidade.PUBLICA,
        quem_escreve=Area.QuemEscreve.EQUIPE,
    )


@pytest.fixture
def conversa(sala):
    """Uma conversa com duas falas: a pergunta e uma resposta."""
    autora = Pessoa.objects.create(
        id_da_plataforma="p_ana", email="ana@exemplo.com", nome_exibido="Ana"
    )
    topico = Topico.objects.create(
        area=sala, autor=autora, titulo="A textura estica no braço"
    )
    Mensagem.objects.create(topico=topico, autor=autora, texto="Travei no Studio.")
    Mensagem.objects.create(
        topico=topico, autor=autora, texto="Consegui escalando o UV antes."
    )
    return topico


def moderar_topico(client, topico, **campos):
    return client.post(
        reverse("moderar_topico", args=[topico.pk]),
        campos,
        headers={"cookie": COOKIE},
    )


def moderar_mensagem(client, mensagem, **campos):
    return client.post(
        reverse("moderar_mensagem", args=[mensagem.pk]),
        campos,
        headers={"cookie": COOKIE},
    )


def moderar_area(client, area, **campos):
    return client.post(
        reverse("moderar_area", args=[area.slug]),
        campos,
        headers={"cookie": COOKIE},
    )


def ver(client, nome, *args):
    return client.get(reverse(nome, args=args), headers={"cookie": COOKIE})


def campos_da_area(area, **mudancas):
    """O formulário inteiro da área, como o navegador o envia.

    Ele manda os quatro campos sempre, e não só o que mudou. Um teste que
    mandasse menos provaria uma tela que não existe.
    """
    campos = {
        "acao": "salvar",
        "nome": area.nome,
        "descricao": area.descricao,
        "visibilidade": area.visibilidade,
        "quem_escreve": area.quem_escreve,
    }
    campos.update(mudancas)
    return campos


# ======================================================================
# 1. QUEM ENXERGA E QUEM ALCANÇA — a razão de a tarefa existir
# ======================================================================
def test_o_administrador_ve_as_ferramentas_nas_tres_telas(
    client, env, monkeypatch, conversa
):
    como_dono(monkeypatch)

    for resposta in [
        ver(client, "home"),
        ver(client, "area", conversa.area.slug),
        ver(client, "topico", conversa.pk),
    ]:
        assert resposta.status_code == 200
        assert FERRAMENTAS in resposta.content.decode()


def test_a_aluna_nao_ve_ferramenta_nenhuma(client, env, monkeypatch, conversa):
    como_aluna(monkeypatch)

    for resposta in [
        ver(client, "home"),
        ver(client, "area", conversa.area.slug),
        ver(client, "topico", conversa.pk),
    ]:
        assert resposta.status_code == 200
        assert FERRAMENTAS not in resposta.content.decode()


def test_o_visitante_nao_ve_ferramenta_nenhuma(client, env, monkeypatch, avisos):
    sem_login(monkeypatch)

    for resposta in [ver(client, "home"), ver(client, "area", avisos.slug)]:
        assert resposta.status_code == 200
        assert FERRAMENTAS not in resposta.content.decode()


def test_o_professor_nao_ve_as_ferramentas(client, env, monkeypatch, conversa):
    """A decisão de 30/08/2026, travada: o professor fala com autoridade e
    **não** modera. Não é esquecimento, é a espera de uma decisão do mantenedor
    sobre qual metade da moderação cabe a ele (lei §5)."""
    como_professor(monkeypatch)

    resposta = ver(client, "topico", conversa.pk)
    assert resposta.status_code == 200
    assert FERRAMENTAS not in resposta.content.decode()

    assert moderar_topico(client, conversa, acao="fixar").status_code == 404
    conversa.refresh_from_db()
    assert conversa.fixado is False


def test_a_porta_responde_404_para_quem_nao_e_administrador(
    client, env, monkeypatch, conversa, sala
):
    """**404, nunca 403.** O 403 confirmaria que a porta existe, e um fórum de
    escola não conta a estranhos qual é a estrutura de poder dele."""
    mensagem = conversa.mensagens.first()
    como_aluna(monkeypatch)

    assert moderar_topico(client, conversa, acao="tirar_do_ar").status_code == 404
    assert moderar_mensagem(client, mensagem, acao="tirar_do_ar").status_code == 404
    assert moderar_area(client, sala, acao="arquivar").status_code == 404
    assert (
        client.post(
            reverse("criar_area"),
            {
                "nome": "Área da aluna",
                "visibilidade": "alunos",
                "quem_escreve": "aluno",
            },
            headers={"cookie": COOKIE},
        ).status_code
        == 404
    )

    # E NADA mudou: a recusa não é só de status.
    conversa.refresh_from_db()
    mensagem.refresh_from_db()
    sala.refresh_from_db()
    assert conversa.estado == Topico.Estado.PUBLICADO
    assert mensagem.removida_em is None
    assert sala.ativa is True
    assert Area.objects.count() == 1


def test_a_porta_responde_404_para_visitante(client, env, monkeypatch, avisos):
    sem_login(monkeypatch)
    assert moderar_area(client, avisos, acao="arquivar").status_code == 404
    avisos.refresh_from_db()
    assert avisos.ativa is True


def test_moderar_por_get_nao_existe(client, env, monkeypatch, conversa):
    """Ação de moderação por GET é ação que o robô do Google executa ao passear
    pela página, e que um `<img src>` de outro site dispara."""
    como_dono(monkeypatch)
    resposta = client.get(
        reverse("moderar_topico", args=[conversa.pk]), headers={"cookie": COOKIE}
    )
    assert resposta.status_code == 405


def test_acao_desconhecida_nao_muda_nada(client, env, monkeypatch, conversa):
    como_dono(monkeypatch)
    resposta = moderar_topico(client, conversa, acao="explodir")
    assert resposta.status_code == 400
    conversa.refresh_from_db()
    assert conversa.estado == Topico.Estado.PUBLICADO
    assert conversa.fixado is False


# ======================================================================
# 2. A CONVERSA — editar, mover, fixar, trancar, tirar do ar
# ======================================================================
def test_editar_o_titulo(client, env, monkeypatch, conversa):
    como_dono(monkeypatch)
    resposta = moderar_topico(
        client, conversa, acao="salvar", titulo="A textura estica no braço do avatar"
    )
    assert resposta.status_code == 302
    conversa.refresh_from_db()
    assert conversa.titulo == "A textura estica no braço do avatar"


def test_titulo_curto_demais_e_recusado(client, env, monkeypatch, conversa):
    como_dono(monkeypatch)
    antes = conversa.titulo
    assert (
        moderar_topico(client, conversa, acao="salvar", titulo="oi").status_code == 400
    )
    conversa.refresh_from_db()
    assert conversa.titulo == antes


def test_mover_a_conversa_de_area(client, env, monkeypatch, conversa, avisos):
    """Mover é a condição 6 da lei (§4.6). A conversa vai inteira: as mensagens
    pendem do tópico, não da área."""
    como_dono(monkeypatch)
    resposta = moderar_topico(
        client, conversa, acao="salvar", titulo=conversa.titulo, area_id=avisos.pk
    )
    assert resposta.status_code == 302
    conversa.refresh_from_db()
    assert conversa.area_id == avisos.pk
    assert conversa.mensagens.count() == 2


def test_mover_para_area_que_nao_existe_e_recusado(client, env, monkeypatch, conversa):
    como_dono(monkeypatch)
    resposta = moderar_topico(
        client, conversa, acao="salvar", titulo=conversa.titulo, area_id=99999
    )
    assert resposta.status_code == 400
    conversa.refresh_from_db()
    assert conversa.area.slug == "duvidas"


def test_fixar_e_desafixar(client, env, monkeypatch, conversa):
    como_dono(monkeypatch)

    assert moderar_topico(client, conversa, acao="fixar").status_code == 302
    conversa.refresh_from_db()
    assert conversa.fixado is True

    assert moderar_topico(client, conversa, acao="desafixar").status_code == 302
    conversa.refresh_from_db()
    assert conversa.fixado is False


def test_trancar_faz_a_resposta_da_aluna_ser_recusada(
    client, env, monkeypatch, conversa
):
    """A prova de que trancar não é enfeite de tela: o cadeado é a view de
    resposta, não o formulário escondido."""
    como_dono(monkeypatch)
    assert moderar_topico(client, conversa, acao="trancar").status_code == 302

    como_aluna(monkeypatch)
    recusa = client.post(
        reverse("responder", args=[conversa.pk]),
        {"texto": "posso responder mesmo assim?"},
        headers={"cookie": COOKIE},
    )
    assert recusa.status_code == 403
    assert conversa.mensagens.count() == 2

    como_dono(monkeypatch)
    assert moderar_topico(client, conversa, acao="destrancar").status_code == 302
    como_aluna(monkeypatch)
    assert (
        client.post(
            reverse("responder", args=[conversa.pk]),
            {"texto": "agora vai"},
            headers={"cookie": COOKIE},
        ).status_code
        == 302
    )
    assert conversa.mensagens.count() == 3


def test_tirar_a_conversa_do_ar_nao_apaga_nada(client, env, monkeypatch, conversa):
    """ "Deletar" nesta casa é tirar do ar. A linha continua no banco, e é ela
    que permite reconstruir o que houve numa denúncia."""
    como_dono(monkeypatch)
    assert moderar_topico(client, conversa, acao="tirar_do_ar").status_code == 302

    conversa.refresh_from_db()
    assert conversa.estado == Topico.Estado.REMOVIDO
    assert Topico.objects.count() == 1
    assert Mensagem.objects.count() == 2

    # Para a aluna, sumiu de verdade: 404 na conversa e fora da lista da área.
    como_aluna(monkeypatch)
    assert ver(client, "topico", conversa.pk).status_code == 404
    lista = ver(client, "area", conversa.area.slug).content.decode()
    assert conversa.titulo not in lista

    # E continua ali para quem pode devolvê-la ao ar.
    como_dono(monkeypatch)
    tela = ver(client, "topico", conversa.pk)
    assert tela.status_code == 200
    assert "fora do ar" in tela.content.decode()


def test_devolver_a_conversa_ao_ar(client, env, monkeypatch, conversa):
    como_dono(monkeypatch)
    moderar_topico(client, conversa, acao="tirar_do_ar")
    assert moderar_topico(client, conversa, acao="restaurar").status_code == 302

    conversa.refresh_from_db()
    assert conversa.estado == Topico.Estado.PUBLICADO
    como_aluna(monkeypatch)
    assert ver(client, "topico", conversa.pk).status_code == 200


def test_apontar_a_resposta_certa_e_tirar_o_selo(client, env, monkeypatch, conversa):
    """O selo de resolvido (lei §5): é o que transforma o fórum em patrimônio da
    escola em vez de arquivo morto."""
    resposta_boa = conversa.mensagens.last()
    como_dono(monkeypatch)

    assert (
        moderar_topico(
            client, conversa, acao="aceitar", mensagem_id=resposta_boa.pk
        ).status_code
        == 302
    )
    conversa.refresh_from_db()
    assert conversa.resposta_aceita_id == resposta_boa.pk

    assert moderar_topico(client, conversa, acao="desmarcar").status_code == 302
    conversa.refresh_from_db()
    assert conversa.resposta_aceita_id is None


def test_nao_aceita_resposta_de_outra_conversa(
    client, env, monkeypatch, conversa, sala
):
    outra = Topico.objects.create(
        area=sala, autor=conversa.autor, titulo="Outra conversa"
    )
    intrusa = Mensagem.objects.create(
        topico=outra, autor=conversa.autor, texto="fala de outro lugar"
    )
    como_dono(monkeypatch)

    resposta = moderar_topico(client, conversa, acao="aceitar", mensagem_id=intrusa.pk)
    assert resposta.status_code == 400
    conversa.refresh_from_db()
    assert conversa.resposta_aceita_id is None


# ======================================================================
# 3. A MENSAGEM — editar (e dizer que editou) e tirar do ar
# ======================================================================
def test_editar_a_mensagem_marca_a_edicao_e_reindexa_a_busca(
    client, env, monkeypatch, conversa
):
    """Duas coisas num teste só porque elas falham juntas na vida real: quem
    esquece de reindexar deixa o texto novo invisível para a busca **e** o
    antigo achável, sem erro em lugar nenhum."""
    mensagem = conversa.mensagens.first()
    como_dono(monkeypatch)

    resposta = moderar_mensagem(
        client, mensagem, acao="salvar", texto="Travei na exportação do modelo."
    )
    assert resposta.status_code == 302

    mensagem.refresh_from_db()
    assert mensagem.texto == "Travei na exportação do modelo."
    assert mensagem.editado_em is not None, (
        "editar em silêncio a fala de outra pessoa é o que um fórum não pode "
        "fazer: quem respondeu confiando no texto antigo precisa ver que mudou"
    )

    acha_o_novo = Mensagem.objects.filter(
        pk=mensagem.pk, busca=SearchQuery("exportação", config="portuguese")
    )
    assert acha_o_novo.exists(), "a busca ficou com o texto velho indexado"
    acha_o_velho = Mensagem.objects.filter(
        pk=mensagem.pk, busca=SearchQuery("Studio", config="portuguese")
    )
    assert not acha_o_velho.exists()


def test_mensagem_vazia_e_recusada(client, env, monkeypatch, conversa):
    mensagem = conversa.mensagens.first()
    como_dono(monkeypatch)

    assert (
        moderar_mensagem(client, mensagem, acao="salvar", texto="   ").status_code
        == 400
    )
    mensagem.refresh_from_db()
    assert mensagem.texto == "Travei no Studio."


def test_tirar_a_mensagem_do_ar_nao_apaga_e_tira_o_selo(
    client, env, monkeypatch, conversa
):
    premiada = conversa.mensagens.last()
    como_dono(monkeypatch)
    moderar_topico(client, conversa, acao="aceitar", mensagem_id=premiada.pk)

    assert moderar_mensagem(client, premiada, acao="tirar_do_ar").status_code == 302

    premiada.refresh_from_db()
    conversa.refresh_from_db()
    assert premiada.removida_em is not None
    assert Mensagem.objects.count() == 2, "a mensagem não pode sair do banco"
    assert conversa.resposta_aceita_id is None, (
        "uma mensagem fora do ar não pode continuar sendo a resposta premiada: "
        "o selo apontaria para o vazio"
    )

    # A aluna não lê o que saiu do ar; o administrador lê, marcado.
    como_aluna(monkeypatch)
    assert premiada.texto not in ver(client, "topico", conversa.pk).content.decode()
    como_dono(monkeypatch)
    assert premiada.texto in ver(client, "topico", conversa.pk).content.decode()


def test_devolver_a_mensagem_ao_ar(client, env, monkeypatch, conversa):
    mensagem = conversa.mensagens.first()
    como_dono(monkeypatch)
    moderar_mensagem(client, mensagem, acao="tirar_do_ar")

    assert moderar_mensagem(client, mensagem, acao="restaurar").status_code == 302
    mensagem.refresh_from_db()
    assert mensagem.removida_em is None

    como_aluna(monkeypatch)
    assert mensagem.texto in ver(client, "topico", conversa.pk).content.decode()


# ======================================================================
# 4. A ÁREA — deixar privada, abrir ao mundo, arquivar, criar
# ======================================================================
def test_deixar_a_area_privada(client, env, monkeypatch, avisos):
    """ "Deixar privado", com as palavras do pedido: o que era aberto ao mundo
    passa a exigir matrícula."""
    como_dono(monkeypatch)
    resposta = moderar_area(
        client, avisos, **campos_da_area(avisos, visibilidade="alunos")
    )
    assert resposta.status_code == 302

    avisos.refresh_from_db()
    assert avisos.visibilidade == Area.Visibilidade.ALUNOS

    sem_login(monkeypatch)
    assert ver(client, "area", avisos.slug).status_code == 404


def test_abrir_a_area_ao_mundo_exige_que_so_a_escola_fale(
    client, env, monkeypatch, sala
):
    """A regra que protege menor de idade: o que estranho lê sem entrar não
    leva mensagem de aluno. Aqui ela aparece como uma frase, e não como um erro
    de banco."""
    como_dono(monkeypatch)
    resposta = moderar_area(
        client, sala, **campos_da_area(sala, visibilidade="publica")
    )
    assert resposta.status_code == 400
    assert "só a escola" in resposta.content.decode()

    sala.refresh_from_db()
    assert sala.visibilidade == Area.Visibilidade.ALUNOS


def test_abrir_a_area_ao_mundo_com_a_escola_falando(client, env, monkeypatch, sala):
    como_dono(monkeypatch)
    resposta = moderar_area(
        client,
        sala,
        **campos_da_area(sala, visibilidade="publica", quem_escreve="equipe"),
    )
    assert resposta.status_code == 302

    sala.refresh_from_db()
    assert sala.visibilidade == Area.Visibilidade.PUBLICA

    sem_login(monkeypatch)
    assert ver(client, "area", sala.slug).status_code == 200


def test_editar_nome_e_descricao_da_area(client, env, monkeypatch, sala):
    como_dono(monkeypatch)
    resposta = moderar_area(
        client,
        sala,
        **campos_da_area(sala, nome="Dúvidas de modelagem", descricao="Pergunte aqui."),
    )
    assert resposta.status_code == 302

    sala.refresh_from_db()
    assert sala.nome == "Dúvidas de modelagem"
    assert sala.descricao == "Pergunte aqui."
    assert sala.slug == "duvidas", (
        "o endereço não pode acompanhar o nome: cada renomeação quebraria todos "
        "os links já compartilhados"
    )


def test_area_sem_nome_e_recusada(client, env, monkeypatch, sala):
    como_dono(monkeypatch)
    assert (
        moderar_area(client, sala, **campos_da_area(sala, nome="  ")).status_code == 400
    )
    sala.refresh_from_db()
    assert sala.nome == "Dúvidas gerais"


def test_arquivar_a_area_some_para_a_aluna_e_continua_para_o_dono(
    client, env, monkeypatch, conversa, sala
):
    """Arquivar é o "deletar" honesto: some da lista de todo mundo, e nada sai
    do banco. E tem volta, senão seria porta de mão única."""
    como_dono(monkeypatch)
    assert moderar_area(client, sala, acao="arquivar").status_code == 302

    sala.refresh_from_db()
    assert sala.ativa is False
    assert Area.objects.count() == 1
    assert Topico.objects.count() == 1

    como_aluna(monkeypatch)
    assert ver(client, "area", sala.slug).status_code == 404
    assert ver(client, "topico", conversa.pk).status_code == 404
    assert sala.nome not in ver(client, "home").content.decode()

    como_dono(monkeypatch)
    capa = ver(client, "home").content.decode()
    assert sala.nome in capa
    assert "arquivada" in capa
    assert ver(client, "area", sala.slug).status_code == 200


def test_reabrir_a_area(client, env, monkeypatch, sala):
    como_dono(monkeypatch)
    moderar_area(client, sala, acao="arquivar")
    assert moderar_area(client, sala, acao="reabrir").status_code == 302

    sala.refresh_from_db()
    assert sala.ativa is True
    como_aluna(monkeypatch)
    assert ver(client, "area", sala.slug).status_code == 200


def criar_area(client, **campos):
    return client.post(reverse("criar_area"), campos, headers={"cookie": COOKIE})


def test_criar_uma_area_nova(client, env, monkeypatch):
    como_dono(monkeypatch)
    resposta = criar_area(
        client,
        nome="Dicas de textura",
        descricao="O que funciona e o que não funciona.",
        visibilidade="alunos",
        quem_escreve="aluno",
    )
    assert resposta.status_code == 302

    nova = Area.objects.get(slug="dicas-de-textura")
    assert nova.nome == "Dicas de textura"
    assert nova.visibilidade == Area.Visibilidade.ALUNOS
    assert resposta["Location"].endswith("/a/dicas-de-textura")

    como_aluna(monkeypatch)
    assert nova.nome in ver(client, "home").content.decode()


def test_criar_area_publica_onde_o_aluno_escreve_e_recusado(client, env, monkeypatch):
    como_dono(monkeypatch)
    resposta = criar_area(
        client, nome="Vitrine", visibilidade="publica", quem_escreve="aluno"
    )
    assert resposta.status_code == 400
    assert Area.objects.count() == 0


def test_criar_area_com_endereco_repetido_e_recusado(client, env, monkeypatch, sala):
    como_dono(monkeypatch)
    resposta = criar_area(
        client, nome="Dúvidas gerais", visibilidade="alunos", quem_escreve="aluno"
    )
    assert resposta.status_code == 400
    assert Area.objects.count() == 1


def test_criar_area_sem_letra_no_nome_e_recusado(client, env, monkeypatch):
    """`slugify("...")` devolve string vazia, e uma área sem endereço seria uma
    área que ninguém abre."""
    como_dono(monkeypatch)
    resposta = criar_area(
        client, nome="...", visibilidade="alunos", quem_escreve="aluno"
    )
    assert resposta.status_code == 400
    assert Area.objects.count() == 0


# ======================================================================
# 5. O PERCURSO INTEIRO, COM CSRF LIGADO — o único teste que prova o formulário
# ======================================================================
def test_o_botao_do_administrador_atravessa_o_csrf_de_verdade(
    env, monkeypatch, conversa
):
    """Suíte que só usa o cliente padrão não prova formulário nenhum: ela prova
    a permissão da view e passa por cima da porta de CSRF (`armadilhas/204`).

    O crachá vai no POTE de cookies, e não no cabeçalho: `headers={"cookie":
    ...}` substitui o cabeçalho inteiro e leva junto o `forum_csrf` que a
    página acabou de plantar.
    """
    como_dono(monkeypatch)
    navegador = Client(enforce_csrf_checks=True)
    navegador.cookies["meshcraft_sessao"] = "um-cookie-opaco-qualquer"

    tela = navegador.get(reverse("topico", args=[conversa.pk]))
    assert tela.status_code == 200
    achado = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', tela.content)
    assert achado, "a tela do administrador não imprimiu o token de CSRF"

    resposta = navegador.post(
        reverse("moderar_topico", args=[conversa.pk]),
        {"acao": "fixar", "csrfmiddlewaretoken": achado.group(1).decode()},
    )
    assert resposta.status_code == 302, resposta.content[:400]
    conversa.refresh_from_db()
    assert conversa.fixado is True
