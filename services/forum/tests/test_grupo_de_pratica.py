"""Guardas do GRUPO DE PRÁTICA da Comunidade Meshcraft (TAR-824, 27/09/2026).

O grupo é uma área de TURMA com responsável da escola e vaga máxima, e quem
entra nela é quem tem VÍNCULO ATIVO: uma linha própria, com quem adicionou, o
motivo, desde quando e até quando. Remover nunca apaga a linha, preenche `ate`.

**Os testes de porta atravessam a rede, não a função.** Monta-se o mundo,
dubla-se a `identidade` e a `alunos`, e pede-se a URL como um navegador pediria
(o motivo está no cabeçalho de `test_escrever.py`).
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core import moderacao, views
from apps.core.permissoes import areas_visiveis, pode_escrever, pode_ler
from apps.core.sessao import Ator
from apps.forum.models import Area, MembroDoGrupo, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db

COOKIE = "meshcraft_sessao=um-cookie-opaco-qualquer"


def sessao_de(pessoa: Pessoa) -> dict:
    return {
        "autenticado": True,
        "id": pessoa.id_da_plataforma,
        "email": pessoa.email,
        "nome_exibido": pessoa.nome_exibido,
    }


@pytest.fixture
def env(monkeypatch):
    """As duas listas de poder preenchidas com pessoas DIFERENTES."""
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


def como(monkeypatch, pessoa: Pessoa, categoria: str = "aluno"):
    dublar(monkeypatch, sessao=sessao_de(pessoa), categoria=categoria)


@pytest.fixture
def professora():
    return Pessoa.objects.create(
        id_da_plataforma="p_prof", email="prof@exemplo.com", nome_exibido="Profa. Lia"
    )


@pytest.fixture
def ana():
    return Pessoa.objects.create(
        id_da_plataforma="p_ana", email="ana@exemplo.com", nome_exibido="Ana"
    )


@pytest.fixture
def bia():
    return Pessoa.objects.create(
        id_da_plataforma="p_bia", email="bia@exemplo.com", nome_exibido="Bia"
    )


def novo_grupo(slug: str, responsavel: Pessoa, vagas: int = 10) -> Area:
    return Area.objects.create(
        slug=slug,
        nome=f"Grupo {slug}",
        visibilidade=Area.Visibilidade.TURMA,
        quem_escreve=Area.QuemEscreve.ALUNO,
        curso_id="modelagem-1",
        responsavel=responsavel,
        vagas=vagas,
    )


@pytest.fixture
def grupo(professora):
    return novo_grupo("grupo-azul", professora)


@pytest.fixture
def outro_grupo(professora):
    return novo_grupo("grupo-verde", professora)


def vincular(grupo: Area, pessoa: Pessoa, quem: Pessoa) -> MembroDoGrupo:
    return MembroDoGrupo.objects.create(
        grupo=grupo, pessoa=pessoa, adicionado_por=quem, motivo="turma de setembro"
    )


def duvida(grupo: Area, autor: Pessoa, titulo: str, texto: str) -> Topico:
    topico = Topico.objects.create(area=grupo, autor=autor, titulo=titulo)
    mensagem = Mensagem.objects.create(topico=topico, autor=autor, texto=texto)
    mensagem.indexar_para_busca()
    return topico


def pedir(client, nome, *args, **query):
    return client.get(reverse(nome, args=args), query, headers={"cookie": COOKIE})


def gerir(client, grupo, **dados):
    return client.post(
        reverse("membros_do_grupo", args=[grupo.slug]),
        dados,
        headers={"cookie": COOKIE},
    )


# ------------------------------------------------------------ o vínculo


def test_um_vinculo_ativo_por_pessoa_e_grupo_e_garantido_pelo_banco(
    grupo, ana, professora
):
    """Duas linhas ativas para a mesma pessoa no mesmo grupo não chegam a existir.

    E a saída não apaga nada: depois de `ate` preenchido, uma entrada nova é
    uma linha nova, e a antiga continua contando a história.
    """
    primeira = vincular(grupo, ana, professora)
    with pytest.raises(IntegrityError), transaction.atomic():
        vincular(grupo, ana, professora)

    primeira.ate = timezone.now()
    primeira.removido_por = professora
    primeira.save()
    vincular(grupo, ana, professora)
    assert MembroDoGrupo.objects.filter(grupo=grupo, pessoa=ana).count() == 2


def test_a_saida_sem_quem_removeu_e_recusada_pelo_banco(grupo, ana, professora):
    vinculo = vincular(grupo, ana, professora)
    with pytest.raises(IntegrityError), transaction.atomic():
        MembroDoGrupo.objects.filter(pk=vinculo.pk).update(ate=timezone.now())


# ------------------------------------------------------------ a regra de leitura


def test_membro_le_o_grupo_e_aluno_de_outro_grupo_nao(
    grupo, outro_grupo, ana, bia, professora
):
    vincular(grupo, ana, professora)
    vincular(outro_grupo, bia, professora)
    a_ana = Ator(pessoa=ana, eh_aluno=True)
    a_bia = Ator(pessoa=bia, eh_aluno=True)

    assert pode_ler(grupo, a_ana) is True
    assert pode_escrever(grupo, a_ana) is True
    assert pode_ler(grupo, a_bia) is False
    assert pode_escrever(grupo, a_bia) is False
    assert grupo.pk in {a.pk for a in areas_visiveis(a_ana)}
    assert grupo.pk not in {a.pk for a in areas_visiveis(a_bia)}


def test_vinculo_sem_matricula_nao_abre_o_grupo(grupo, ana, professora):
    """Entra quem tem conta E matrícula ativa (decisão 3 da rota).

    A `alunos` fora do ar chega aqui como `eh_aluno=False`, e a porta fica
    fechada: nunca aberta por falta de resposta.
    """
    vincular(grupo, ana, professora)
    assert pode_ler(grupo, Ator(pessoa=ana)) is False


def test_a_equipe_le_todo_grupo_sem_vinculo(grupo, professora):
    assert pode_ler(grupo, Ator(pessoa=professora, eh_professor=True)) is True


def test_aluno_de_outro_grupo_recebe_404_nao_ve_na_lista_e_nao_acha_na_busca(
    client, env, monkeypatch, grupo, outro_grupo, ana, bia, professora
):
    vincular(grupo, ana, professora)
    vincular(outro_grupo, bia, professora)
    topico = duvida(grupo, ana, "Minha textura estica", "a textura do escudo estica")

    como(monkeypatch, bia)
    assert pedir(client, "area", grupo.slug).status_code == 404
    assert pedir(client, "topico", topico.pk).status_code == 404
    assert grupo.nome not in pedir(client, "home").content.decode()
    busca = pedir(client, "buscar", q="escudo").content.decode()
    assert "Minha textura estica" not in busca

    como(monkeypatch, ana)
    assert pedir(client, "area", grupo.slug).status_code == 200
    assert pedir(client, "topico", topico.pk).status_code == 200
    assert grupo.nome in pedir(client, "home").content.decode()
    assert (
        "Minha textura estica" in pedir(client, "buscar", q="escudo").content.decode()
    )


def test_remover_fecha_leitura_busca_e_a_comunidade_e_guarda_a_linha(
    client, env, monkeypatch, grupo, ana, bia, professora
):
    vinculo = vincular(grupo, ana, professora)
    vincular(grupo, bia, professora)
    topico = duvida(grupo, bia, "Como exporto o rig", "o rig do dragão quebra")

    como(monkeypatch, ana)
    assert pedir(client, "area", grupo.slug).status_code == 200
    assert "Como exporto o rig" in pedir(client, "comunidade").content.decode()

    como(monkeypatch, professora, categoria="cadastrado")
    resposta = gerir(
        client, grupo, acao="remover", vinculo_id=vinculo.pk, motivo="pediu"
    )
    assert resposta.status_code == 302

    como(monkeypatch, ana)
    assert pedir(client, "area", grupo.slug).status_code == 404
    assert pedir(client, "topico", topico.pk).status_code == 404
    assert (
        "Como exporto o rig" not in pedir(client, "buscar", q="dragão").content.decode()
    )
    assert grupo.nome not in pedir(client, "home").content.decode()
    assert "Como exporto o rig" not in pedir(client, "comunidade").content.decode()

    vinculo.refresh_from_db()
    assert vinculo.ate is not None
    assert vinculo.removido_por == professora


# ------------------------------------------------------------ a gestão da equipe


def test_a_equipe_adiciona_membro_e_a_linha_guarda_quem_e_por_que(
    client, env, monkeypatch, grupo, ana, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    tela = pedir(client, "membros_do_grupo", grupo.slug)
    assert tela.status_code == 200
    assert "ana@exemplo.com" not in tela.content.decode()

    resposta = gerir(
        client, grupo, acao="adicionar", email="Ana@Exemplo.com", motivo="turma 9"
    )
    assert resposta.status_code == 302
    vinculo = MembroDoGrupo.objects.get(grupo=grupo, pessoa=ana)
    assert vinculo.adicionado_por == professora
    assert vinculo.motivo == "turma 9"
    assert vinculo.ate is None
    tela = pedir(client, "membros_do_grupo", grupo.slug).content.decode()
    assert "Ana" in tela
    assert "ana@exemplo.com" not in tela


def test_vaga_cheia_recusa(client, env, monkeypatch, professora, ana, bia):
    grupo = novo_grupo("grupo-pequeno", professora, vagas=1)
    vincular(grupo, ana, professora)

    como(monkeypatch, professora, categoria="cadastrado")
    resposta = gerir(client, grupo, acao="adicionar", email=bia.email, motivo="x")
    assert resposta.status_code == 400
    assert moderacao.ERRO_VAGA_CHEIA in resposta.content.decode()
    assert MembroDoGrupo.objects.filter(grupo=grupo, ate__isnull=True).count() == 1


def test_quem_nao_e_equipe_recebe_404_nas_telas_de_gestao(
    client, env, monkeypatch, grupo, ana, bia, professora
):
    vincular(grupo, ana, professora)
    como(monkeypatch, ana)
    assert pedir(client, "membros_do_grupo", grupo.slug).status_code == 404
    assert (
        gerir(client, grupo, acao="adicionar", email=bia.email, motivo="x").status_code
        == 404
    )
    criar = client.post(
        reverse("criar_area"),
        {
            "nome": "Grupo pirata",
            "visibilidade": "turma",
            "quem_escreve": "aluno",
            "curso_id": "c",
            "responsavel": ana.pk,
            "vagas": "5",
        },
        headers={"cookie": COOKIE},
    )
    assert criar.status_code == 404
    assert not MembroDoGrupo.objects.filter(pessoa=bia).exists()
    assert not Area.objects.filter(nome="Grupo pirata").exists()

    dublar(monkeypatch, sessao={"autenticado": False})
    assert pedir(client, "membros_do_grupo", grupo.slug).status_code == 404


def test_a_equipe_cria_o_grupo_com_responsavel_vagas_e_curso(
    client, env, monkeypatch, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = client.post(
        reverse("criar_area"),
        {
            "nome": "Grupo das quartas",
            "visibilidade": "turma",
            "quem_escreve": "aluno",
            "curso_id": "modelagem-1",
            "responsavel": professora.pk,
            "vagas": "12",
        },
        headers={"cookie": COOKIE},
    )
    assert resposta.status_code == 302
    grupo = Area.objects.get(nome="Grupo das quartas")
    assert grupo.visibilidade == Area.Visibilidade.TURMA
    assert grupo.responsavel == professora
    assert grupo.vagas == 12
    assert grupo.curso_id == "modelagem-1"


def test_o_responsavel_precisa_ser_da_equipe(client, env, monkeypatch, professora, ana):
    como(monkeypatch, professora, categoria="cadastrado")
    resposta = client.post(
        reverse("criar_area"),
        {
            "nome": "Grupo da Ana",
            "visibilidade": "turma",
            "quem_escreve": "aluno",
            "curso_id": "modelagem-1",
            "responsavel": ana.pk,
            "vagas": "12",
        },
        headers={"cookie": COOKIE},
    )
    assert resposta.status_code == 400
    assert moderacao.ERRO_RESPONSAVEL_FORA_DA_EQUIPE in resposta.content.decode()
    assert not Area.objects.filter(nome="Grupo da Ana").exists()


def test_editar_o_grupo_pela_tela_nao_o_transforma_em_area_de_alunos(
    client, env, monkeypatch, grupo, professora
):
    """A tela de editar área só conhecia `alunos` e `publica`.

    Salvar um grupo por ela, sem a opção `turma`, abriria o grupo para todo
    aluno da escola. A tela oferece a opção marcada e o salvar a preserva.
    """
    como(monkeypatch, professora, categoria="cadastrado")
    tela = pedir(client, "area", grupo.slug).content.decode()
    assert 'value="turma" selected' in tela

    resposta = client.post(
        reverse("moderar_area", args=[grupo.slug]),
        {
            "acao": "salvar",
            "nome": "Grupo azul renomeado",
            "descricao": "",
            "visibilidade": "turma",
            "quem_escreve": "aluno",
            "curso_id": "modelagem-2",
            "responsavel": professora.pk,
            "vagas": "8",
        },
        headers={"cookie": COOKIE},
    )
    assert resposta.status_code == 302
    grupo.refresh_from_db()
    assert grupo.visibilidade == Area.Visibilidade.TURMA
    assert grupo.curso_id == "modelagem-2"
    assert grupo.vagas == 8


def test_a_tela_de_membros_atravessa_o_csrf_de_verdade(
    env, monkeypatch, grupo, ana, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    navegador = Client(enforce_csrf_checks=True)
    navegador.cookies["meshcraft_sessao"] = "um-cookie-opaco-qualquer"
    endereco = reverse("membros_do_grupo", args=[grupo.slug])

    sem_token = navegador.post(
        endereco, {"acao": "adicionar", "email": ana.email, "motivo": "x"}
    )
    assert sem_token.status_code == 403

    corpo = navegador.get(endereco).content.decode()
    marca = 'name="csrfmiddlewaretoken" value="'
    token = corpo.split(marca, 1)[1].split('"', 1)[0]
    com_token = navegador.post(
        endereco,
        {
            "acao": "adicionar",
            "email": ana.email,
            "motivo": "x",
            "csrfmiddlewaretoken": token,
        },
    )
    assert com_token.status_code == 302, com_token.content[:400]
    assert MembroDoGrupo.objects.filter(grupo=grupo, pessoa=ana).exists()


# ------------------------------------------------------------ a página Comunidade


def test_a_comunidade_sem_login_fecha_a_porta_com_texto(client, env, monkeypatch):
    dublar(monkeypatch, sessao={"autenticado": False})
    resposta = pedir(client, "comunidade")
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Entre para ver a sua Comunidade" in corpo
    assert "Quem depende de você" not in corpo
    assert views.CONTRIBUICOES_URL not in corpo


def test_a_comunidade_fecha_para_quem_nao_tem_matricula(
    client, env, monkeypatch, grupo, ana, professora
):
    """Vale também para a `alunos` fora do ar: a porta fica fechada, com texto."""
    vincular(grupo, ana, professora)
    como(monkeypatch, ana, categoria="cadastrado")
    corpo = pedir(client, "comunidade").content.decode()
    assert "A Comunidade é de quem está matriculado" in corpo
    assert grupo.nome not in corpo
    assert views.CONTRIBUICOES_URL not in corpo


def test_a_comunidade_sem_grupo_diz_como_pedir_a_entrada(client, env, monkeypatch, ana):
    como(monkeypatch, ana)
    corpo = pedir(client, "comunidade").content.decode()
    assert "Você ainda não está em um grupo de prática" in corpo
    assert "Quem responde é a equipe da escola" in corpo
    assert reverse("abrir_conversa") in corpo
    assert f'href="{views.CONTRIBUICOES_URL}"' in corpo


def test_a_comunidade_sem_grupo_da_equipe_tambem_aponta_as_contribuicoes(
    client, env, monkeypatch, professora
):
    como(monkeypatch, professora, categoria="cadastrado")
    corpo = pedir(client, "comunidade").content.decode()
    assert "Você ainda não responde por nenhum grupo de prática" in corpo
    assert f'href="{views.CONTRIBUICOES_URL}"' in corpo


def test_a_comunidade_com_grupo_mostra_o_desafio_e_quem_depende_de_voce(
    client, env, monkeypatch, grupo, ana, bia, professora
):
    vincular(grupo, ana, professora)
    vincular(grupo, bia, professora)
    agora = timezone.now()
    nova = duvida(grupo, bia, "Duvida nova da Bia", "a")
    antiga = duvida(grupo, bia, "Duvida antiga da Bia", "b")
    resolvida = duvida(grupo, bia, "Duvida resolvida da Bia", "c")
    duvida(grupo, ana, "Duvida da propria Ana", "d")
    Topico.objects.filter(pk=nova.pk).update(criado_em=agora - timedelta(hours=5))
    Topico.objects.filter(pk=antiga.pk).update(criado_em=agora - timedelta(days=3))
    resposta_certa = Mensagem.objects.create(topico=resolvida, autor=ana, texto="ok")
    Topico.objects.filter(pk=resolvida.pk).update(resposta_aceita=resposta_certa)

    como(monkeypatch, ana)
    corpo = pedir(client, "comunidade").content.decode()

    assert grupo.nome in corpo
    assert 'href="/cursos/modelagem-1/"' in corpo
    assert f'{reverse("area", args=[grupo.slug])}#abrir' in corpo
    assert "Profa. Lia" in corpo
    assert "Quem depende de você" in corpo
    assert corpo.index("Duvida antiga da Bia") < corpo.index("Duvida nova da Bia")
    assert "há 3 dias" in corpo
    assert "há 5 horas" in corpo
    assert "Duvida resolvida da Bia" not in corpo
    assert "Duvida da propria Ana" not in corpo


def test_a_comunidade_com_grupo_vazio_diz_que_ninguem_espera(
    client, env, monkeypatch, grupo, ana, professora
):
    vincular(grupo, ana, professora)
    como(monkeypatch, ana)
    corpo = pedir(client, "comunidade").content.decode()
    assert "Ninguém do seu grupo está esperando resposta agora" in corpo
    assert f'href="{views.CONTRIBUICOES_URL}"' in corpo


def test_a_home_mostra_o_link_da_comunidade_so_para_quem_entrou(
    client, env, monkeypatch, ana
):
    dublar(monkeypatch, sessao={"autenticado": False})
    assert reverse("comunidade") not in pedir(client, "home").content.decode()
    como(monkeypatch, ana)
    assert reverse("comunidade") in pedir(client, "home").content.decode()


def test_o_formulario_do_grupo_traz_o_molde_de_pedido_de_ajuda(
    client, env, monkeypatch, grupo, ana, professora
):
    vincular(grupo, ana, professora)
    como(monkeypatch, ana)
    corpo = pedir(client, "area", grupo.slug).content.decode()
    assert 'id="abrir"' in corpo
    assert "Como pedir ajuda ao grupo" in corpo
    assert "/conquistas/" in corpo

    comum = Area.objects.create(
        slug="duvidas",
        nome="Dúvidas",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.ALUNO,
    )
    assert (
        "Como pedir ajuda ao grupo"
        not in pedir(client, "area", comum.slug).content.decode()
    )
