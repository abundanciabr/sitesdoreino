"""Guardas de TAR-912: o grupo do fórum fecha quando a matrícula para, e reabre
quando ela volta.

Prova, com PostgreSQL de verdade, que fechar e reabrir o grupo de TURMA é
efeito puro da categoria que a `alunos` devolve, sem qualquer mudança em
`MembroDoGrupo`: a linha do vínculo é a mesma do início ao fim, sem duplicar.
Nada aqui concede um poder novo, o direito já é o de `pode_ler`
(`apps/core/permissoes.py`) e `grupos_de` (`apps/core/views.py`) - esta suíte
só mede o que já existe.

As categorias reais de matrícula (`contracts/alunos.openapi.yaml`,
`getStudentStanding`): `pausado` é a ficha `suspensa`, `ex_aluno` é a ficha
`encerrada`, e só `aluno` abre a porta. O fórum não lê o banco da `alunos`
(Lei 3 da Constituição) - a fonte da verdade sobre os nomes é o contrato
congelado que esta célula já consome.
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

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
    for nome, valor in [
        ("IDENTIDADE_API_URL", "http://identidade:8000/interno"),
        ("IDENTIDADE_API_TOKEN", "tok-id"),
        ("ALUNOS_API_URL", "http://alunos:8000/api/alunos"),
        ("ALUNOS_API_TOKEN", "tok-al"),
        ("FORUM_PROFESSORES", "prof@exemplo.com"),
        ("ADMIN_EMAILS", "dono@exemplo.com"),
    ]:
        monkeypatch.setenv(nome, valor)


def dublar(monkeypatch, *, sessao=None, categoria=None, alunos_fora_do_ar=False):
    """A rede das duas células vizinhas, dublada por URL.

    `alunos_fora_do_ar=True` simula a `alunos` sem responder: o mesmo caminho
    que a produção atravessa quando a rede cai (`AlunosIndisponivel` em
    `apps/core/clients.py`), tratado por `quem_e` como matrícula ausente, nunca
    como sucesso.
    """

    def falso_get(self, url, **kwargs):
        endereco = str(url)
        if "identidade" in endereco:
            if sessao is None:
                raise AssertionError(f"chamada inesperada à identidade: {endereco}")
            return httpx.Response(200, json=sessao)
        if alunos_fora_do_ar:
            raise httpx.ConnectError("a alunos não respondeu (simulado)")
        if categoria is None:
            raise AssertionError(f"chamada inesperada à alunos: {endereco}")
        return httpx.Response(200, json={"categoria": categoria})

    monkeypatch.setattr(httpx.Client, "get", falso_get)


def como(
    monkeypatch, pessoa: Pessoa, categoria: str = "aluno", *, alunos_fora_do_ar=False
):
    dublar(
        monkeypatch,
        sessao=sessao_de(pessoa),
        categoria=categoria,
        alunos_fora_do_ar=alunos_fora_do_ar,
    )


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


@pytest.fixture
def grupo(professora):
    return Area.objects.create(
        slug="grupo-saida-e-retorno",
        nome="Grupo Saída e Retorno",
        visibilidade=Area.Visibilidade.TURMA,
        quem_escreve=Area.QuemEscreve.ALUNO,
        curso_id="modelagem-1",
        responsavel=professora,
        vagas=10,
    )


def vincular(grupo: Area, pessoa: Pessoa, quem: Pessoa) -> MembroDoGrupo:
    return MembroDoGrupo.objects.create(
        grupo=grupo, pessoa=pessoa, adicionado_por=quem, motivo="turma de setembro"
    )


def duvida(grupo: Area, autor: Pessoa, titulo: str, texto: str) -> Topico:
    topico = Topico.objects.create(area=grupo, autor=autor, titulo=titulo)
    mensagem = Mensagem.objects.create(topico=topico, autor=autor, texto=texto)
    mensagem.indexar_para_busca()
    return topico


def pedir(client: Client, nome: str, *args, **query):
    return client.get(reverse(nome, args=args), query, headers={"cookie": COOKIE})


def tentar_escrever(client: Client, grupo: Area, **dados):
    return client.post(
        reverse("novo_topico", args=[grupo.slug]), dados, headers={"cookie": COOKIE}
    )


# --------------------------------------------------------------------------
# A prova principal: fecha com a matrícula parada, reabre com ela de volta.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "estado_fechado", ["pausado", "ex_aluno", "reembolsado", "cadastrado"]
)
def test_matricula_suspensa_ou_encerrada_fecha_o_grupo_e_reativar_reabre_sem_duplicar(
    client, env, monkeypatch, grupo, ana, bia, professora, estado_fechado
):
    """O direito vigente: só a categoria `aluno` abre a porta.

    `pausado` (suspensa), `ex_aluno` (encerrada), `reembolsado` (reembolsada) e
    `cadastrado` fecham igual. Fechar e reabrir não tocam `MembroDoGrupo`: o
    vínculo de Ana é a MESMA linha do começo ao fim, e é a matrícula, nunca o
    vínculo, quem decide.
    """
    vinculo = vincular(grupo, ana, professora)
    vincular(grupo, bia, professora)
    topico = duvida(grupo, bia, "Como exporto o rig", "o rig do dragão quebra")

    # matrícula ativa: lista, busca, acesso por id e os avisos ("quem depende
    # de você", a dúvida de Bia que Ana pode responder) todos abertos.
    como(monkeypatch, ana, categoria="aluno")
    assert pedir(client, "area", grupo.slug).status_code == 200
    assert pedir(client, "topico", topico.pk).status_code == 200
    assert grupo.nome in pedir(client, "home").content.decode()
    assert "Como exporto o rig" in pedir(client, "buscar", q="dragão").content.decode()
    comunidade_aberta = pedir(client, "comunidade").content.decode()
    assert grupo.nome in comunidade_aberta
    assert "Como exporto o rig" in comunidade_aberta

    # a matrícula para: some da lista, da busca, do acesso por id e dos
    # avisos; escrever é recusado pela mesma porta fechada (404).
    como(monkeypatch, ana, categoria=estado_fechado)
    assert pedir(client, "area", grupo.slug).status_code == 404
    assert pedir(client, "topico", topico.pk).status_code == 404
    assert grupo.nome not in pedir(client, "home").content.decode()
    assert (
        "Como exporto o rig" not in pedir(client, "buscar", q="dragão").content.decode()
    )
    comunidade_fechada = pedir(client, "comunidade").content.decode()
    assert grupo.nome not in comunidade_fechada
    assert "Como exporto o rig" not in comunidade_fechada
    assert "A Comunidade é de quem está matriculado" in comunidade_fechada
    resposta = tentar_escrever(
        client, grupo, titulo="Posso tentar ajudar?", texto="tenho uma ideia aqui"
    )
    assert resposta.status_code == 404

    vinculo.refresh_from_db()
    assert vinculo.ate is None, "a matrícula fechou o grupo, não o vínculo"

    # a matrícula volta: reabre com as MESMAS mensagens, sem duplicar o vínculo.
    como(monkeypatch, ana, categoria="aluno")
    assert pedir(client, "area", grupo.slug).status_code == 200
    assert pedir(client, "topico", topico.pk).status_code == 200
    assert grupo.nome in pedir(client, "home").content.decode()
    assert "Como exporto o rig" in pedir(client, "buscar", q="dragão").content.decode()
    comunidade_reaberta = pedir(client, "comunidade").content.decode()
    assert grupo.nome in comunidade_reaberta
    assert "Como exporto o rig" in comunidade_reaberta

    assert Mensagem.objects.filter(topico=topico).count() == 1
    assert MembroDoGrupo.objects.filter(grupo=grupo, pessoa=ana).count() == 1
    vinculo.refresh_from_db()
    assert vinculo.ate is None
    assert vinculo.removido_por is None


def test_alunos_fora_do_ar_fecha_o_grupo_inteiro(
    client, env, monkeypatch, grupo, ana, bia, professora
):
    """Fail-closed também quando a `alunos` não responde, não só quando ela
    responde com uma categoria fechada.

    Não conseguir perguntar nunca é "pode entrar" - o mesmo grupo, com o
    mesmo vínculo ativo, fecha por completo enquanto a rede estiver fora.
    """
    vincular(grupo, ana, professora)
    vincular(grupo, bia, professora)
    topico = duvida(grupo, bia, "Como exporto o rig", "o rig do dragão quebra")

    como(monkeypatch, ana, alunos_fora_do_ar=True)
    assert pedir(client, "area", grupo.slug).status_code == 404
    assert pedir(client, "topico", topico.pk).status_code == 404
    assert grupo.nome not in pedir(client, "home").content.decode()
    assert (
        "Como exporto o rig" not in pedir(client, "buscar", q="dragão").content.decode()
    )
    comunidade = pedir(client, "comunidade").content.decode()
    assert grupo.nome not in comunidade
    assert "A Comunidade é de quem está matriculado" in comunidade

    # e volta a abrir assim que a `alunos` responde de novo, sem tocar o vínculo.
    como(monkeypatch, ana, categoria="aluno")
    assert pedir(client, "area", grupo.slug).status_code == 200
    assert MembroDoGrupo.objects.filter(grupo=grupo, pessoa=ana).count() == 1


def test_vinculo_com_ate_no_passado_fica_fechado_mesmo_com_matricula_ativa(
    client, env, monkeypatch, grupo, ana, professora
):
    """`MembroDoGrupo.ate` no passado é a OUTRA metade da regra de leitura.

    Comportamento real, descrito aqui para quem for ler depois: a matrícula
    ativa sozinha não reabre um vínculo que já saiu do grupo. `pode_ler` exige
    as duas coisas juntas (matrícula ativa E vínculo com `ate` nulo), e uma não
    substitui a outra. Reabrir o vínculo removido é gesto da equipe
    (`tests/test_grupo_de_pratica.py`), não efeito automático da matrícula.
    """
    vinculo = MembroDoGrupo.objects.create(
        grupo=grupo,
        pessoa=ana,
        adicionado_por=professora,
        motivo="turma de agosto",
        desde=timezone.now() - timedelta(days=30),
        ate=timezone.now() - timedelta(days=1),
        removido_por=professora,
    )

    como(monkeypatch, ana, categoria="aluno")
    assert pedir(client, "area", grupo.slug).status_code == 404
    assert grupo.nome not in pedir(client, "home").content.decode()
    comunidade = pedir(client, "comunidade").content.decode()
    assert grupo.nome not in comunidade
    assert "Você ainda não está em um grupo de prática" in comunidade
