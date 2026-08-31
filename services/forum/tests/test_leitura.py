"""Guardas do "TEM COISA NOVA" — a marca-d'água de leitura, na tela.

A fundação existe desde o modelo (lei §4.3) e é aritmética antes de ser
produto: **uma linha por pessoa por ÁREA**, mais as poucas exceções lidas depois
dela. A forma ingênua (uma linha por pessoa por mensagem) fabrica milhões de
linhas para responder "tem coisa nova?" e só se descobre com o fórum cheio.

O que esta suíte trava, além do comportamento visível:

1. **Visitante nunca tem novidade** — sem login não há de quem guardar marca.
2. **Quem nunca leu vê tudo como novo** — é o que convida o aluno que chega.
3. **A poda acontece**: ao marcar tudo como lido, as exceções somem. Sem isso, a
   tabela pequena vira, devagar, a tabela grande que a lei proíbe.

Tudo atravessa a porta pela rede, como no resto da célula.
"""

from __future__ import annotations

import httpx
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.forum.models import Area, MarcaDeLeitura, Mensagem, Pessoa, Topico, TopicoLido

pytestmark = pytest.mark.django_db

COOKIE = "meshcraft_sessao=um-cookie-opaco-qualquer"

SESSAO_DA_ANA = {
    "autenticado": True,
    "id": "p_ana",
    "email": "ana@exemplo.com",
    "nome_exibido": "Ana",
}


@pytest.fixture
def env(monkeypatch):
    for nome, valor in [
        ("IDENTIDADE_API_URL", "http://identidade:8000/interno"),
        ("IDENTIDADE_API_TOKEN", "tok-id"),
        ("ALUNOS_API_URL", "http://alunos:8000/api/alunos"),
        ("ALUNOS_API_TOKEN", "tok-al"),
        ("FORUM_PROFESSORES", ""),
        ("ADMIN_EMAILS", ""),
    ]:
        monkeypatch.setenv(nome, valor)


def dublar(monkeypatch, *, sessao=None, categoria=None):
    def falso_get(self, url, **kwargs):
        if "identidade" in str(url):
            return httpx.Response(200, json=sessao)
        return httpx.Response(200, json={"categoria": categoria})

    monkeypatch.setattr(httpx.Client, "get", falso_get)


def como_aluna(monkeypatch):
    dublar(monkeypatch, sessao=SESSAO_DA_ANA, categoria="aluno")


def sem_login(monkeypatch):
    dublar(monkeypatch, sessao={"autenticado": False})


@pytest.fixture
def sala():
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas gerais",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.ALUNO,
    )


@pytest.fixture
def ana():
    return Pessoa.objects.create(
        id_da_plataforma="p_ana", email="ana@exemplo.com", nome_exibido="Ana"
    )


def conversa(area, autora, titulo="Uma dúvida") -> Topico:
    topico = Topico.objects.create(area=area, autor=autora, titulo=titulo)
    Mensagem.objects.create(topico=topico, autor=autora, texto="a primeira fala")
    return topico


def ver(client, nome, *args):
    return client.get(reverse(nome, args=args), headers={"cookie": COOKIE})


# ======================================================================
# 1. O QUE A PESSOA VÊ
# ======================================================================
def test_quem_nunca_leu_ve_tudo_como_novidade(client, env, monkeypatch, sala, ana):
    """É o caso do aluno que entra pela primeira vez: o fórum o convida em vez
    de parecer vazio."""
    conversa(sala, ana, "A textura estica")
    conversa(sala, ana, "Como exportar o modelo")
    como_aluna(monkeypatch)

    capa = ver(client, "home").content.decode()
    assert "2 novidades" in capa

    area = ver(client, "area", sala.slug).content.decode()
    assert area.count("novidade</span>") == 2


def test_abrir_a_conversa_tira_a_novidade_dela_e_so_dela(
    client, env, monkeypatch, sala, ana
):
    primeira = conversa(sala, ana, "A textura estica")
    conversa(sala, ana, "Como exportar o modelo")
    como_aluna(monkeypatch)

    ver(client, "topico", primeira.pk)

    capa = ver(client, "home").content.decode()
    assert "1 novidade" in capa
    assert "2 novidades" not in capa


def test_uma_resposta_nova_faz_a_conversa_voltar_a_ser_novidade(
    client, env, monkeypatch, sala, ana
):
    """A marca compara com a ÚLTIMA ATIVIDADE do tópico, não com a data em que a
    pessoa passou por ele. Sem isso, uma conversa que recebeu resposta continua
    parecendo lida — e o fórum deixa de avisar justamente quando tem novidade."""
    topico = conversa(sala, ana, "A textura estica")
    como_aluna(monkeypatch)
    ver(client, "topico", topico.pk)
    assert "novidade" not in ver(client, "home").content.decode()

    Topico.objects.filter(pk=topico.pk).update(ultima_atividade_em=timezone.now())

    assert "1 novidade" in ver(client, "home").content.decode()


def test_visitante_nao_tem_novidade_nenhuma(client, env, monkeypatch, ana):
    aberta = Area.objects.create(
        slug="avisos",
        nome="Avisos",
        visibilidade=Area.Visibilidade.PUBLICA,
        quem_escreve=Area.QuemEscreve.EQUIPE,
    )
    conversa(aberta, ana, "Um aviso")
    sem_login(monkeypatch)

    capa = ver(client, "home").content.decode()
    assert "novidade" not in capa
    # E abrir a conversa não guarda marca de ninguém.
    ver(client, "topico", Topico.objects.get().pk)
    assert TopicoLido.objects.count() == 0
    assert MarcaDeLeitura.objects.count() == 0


# ======================================================================
# 2. "JÁ VI TUDO" — e a PODA, que é o que mantém a tabela pequena
# ======================================================================
def test_ja_vi_tudo_zera_as_novidades_e_poda_as_excecoes(
    client, env, monkeypatch, sala, ana
):
    primeira = conversa(sala, ana, "A textura estica")
    conversa(sala, ana, "Como exportar o modelo")
    como_aluna(monkeypatch)
    ver(client, "topico", primeira.pk)
    assert TopicoLido.objects.count() == 1

    resposta = client.post(
        reverse("li_tudo", args=[sala.slug]), {}, headers={"cookie": COOKIE}
    )
    assert resposta.status_code == 302

    assert "novidade" not in ver(client, "home").content.decode()
    assert MarcaDeLeitura.objects.count() == 1, "a marca-d'água é UMA por área"
    assert TopicoLido.objects.count() == 0, (
        "as exceções anteriores à marca têm de ser podadas: sem isso a tabela "
        "pequena vira, devagar, a tabela grande que a lei §4.3 proíbe"
    )


def test_ler_trinta_conversas_cria_trinta_excecoes_e_a_poda_devolve_a_uma_linha(
    client, env, monkeypatch, sala, ana
):
    """O contrato de tamanho, medido: as exceções existem só entre a marca e o
    presente. Trinta conversas abertas viram trinta linhas pequenas; um clique
    em "já vi tudo" devolve tudo a UMA linha por área."""
    topicos = [conversa(sala, ana, f"Dúvida {i}") for i in range(30)]
    como_aluna(monkeypatch)
    for topico in topicos:
        ver(client, "topico", topico.pk)
    assert TopicoLido.objects.count() == 30

    client.post(reverse("li_tudo", args=[sala.slug]), {}, headers={"cookie": COOKIE})

    assert TopicoLido.objects.count() == 0
    assert MarcaDeLeitura.objects.count() == 1


def test_visitante_nao_marca_area_como_lida(client, env, monkeypatch, ana):
    aberta = Area.objects.create(
        slug="avisos",
        nome="Avisos",
        visibilidade=Area.Visibilidade.PUBLICA,
        quem_escreve=Area.QuemEscreve.EQUIPE,
    )
    sem_login(monkeypatch)

    resposta = client.post(
        reverse("li_tudo", args=[aberta.slug]), {}, headers={"cookie": COOKIE}
    )
    assert resposta.status_code == 403
    assert MarcaDeLeitura.objects.count() == 0


def test_o_botao_de_ja_vi_tudo_so_aparece_para_quem_tem_o_que_ver(
    client, env, monkeypatch, sala, ana
):
    conversa(sala, ana, "A textura estica")
    como_aluna(monkeypatch)
    assert "Já vi tudo" in ver(client, "area", sala.slug).content.decode()

    client.post(reverse("li_tudo", args=[sala.slug]), {}, headers={"cookie": COOKIE})
    assert "Já vi tudo" not in ver(client, "area", sala.slug).content.decode()


def test_marcar_por_get_nao_existe(client, env, monkeypatch, sala):
    """Apagar as novidades de alguém tem de ser pedido, nunca consequência de
    abrir um endereço que outro site embutiu numa imagem."""
    como_aluna(monkeypatch)
    resposta = client.get(
        reverse("li_tudo", args=[sala.slug]), headers={"cookie": COOKIE}
    )
    assert resposta.status_code == 405


# ======================================================================
# 3. A NOVIDADE RESPEITA A PERMISSÃO
# ======================================================================
def test_a_contagem_nao_conta_area_que_a_pessoa_nao_ve(
    client, env, monkeypatch, sala, ana
):
    """A conta usa `areas_visiveis`, a mesma função das telas. Se usasse um
    filtro próprio, a capa contaria novidade de área trancada — e o número
    sozinho já entregaria que existe conversa lá dentro."""
    outra = Area.objects.create(
        slug="turma-secreta",
        nome="Turma",
        visibilidade=Area.Visibilidade.TURMA,
        curso_id="curso-x",
        quem_escreve=Area.QuemEscreve.ALUNO,
    )
    conversa(outra, ana, "Conversa da turma")
    conversa(sala, ana, "A textura estica")
    como_aluna(monkeypatch)

    capa = ver(client, "home").content.decode()
    assert "1 novidade" in capa
    assert "Turma" not in capa
