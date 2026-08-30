"""Guardas da ESCRITA — o cadeado que o mantenedor mandou pôr em 30/08/2026.

O mandato, em três frases (registro `20260830-021`, e a §6 da lei do fórum
aponta para lá):

1. **Aluno só escreve atrás do login.** O que é público — aberto ao Google e a
   estranhos — passa a ser só a escola falando.
2. **Só aluno matriculado escreve.** Quem tem cadastro sem ter comprado LÊ e
   não escreve. É o desenho de anti-spam escolhido: para estragar o fórum, a
   pessoa teria que pagar o curso.
3. **A proteção é o cadeado, não a fila de aprovação.** Não há moderação prévia
   nesta porta.

**Todo teste daqui atravessa a porta pela rede, não pela função.** Ninguém aqui
chama `pode_escrever` direto: monta-se o mundo, dubla-se a `identidade` e a
`alunos`, e pede-se a URL como um navegador pediria. Foi exatamente a ausência
disso que deixou uma sabotagem passar por 39 testes verdes nesta célula em
28/08/2026 (a história está no cabeçalho de `test_sessao.py`) — um `Ator`
montado à mão prova o que eu acredito, não o que o site faz.
"""

from __future__ import annotations

import httpx
import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from apps.forum.models import Area, Mensagem, Pessoa, Topico

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
    """O env mínimo dos dois clientes. Sem ele, tudo fecha — e isso é correto."""
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
    """A rede das duas células vizinhas, dublada por URL.

    `sessao=None` significa "esta chamada não deveria acontecer" — e se
    acontecer, o teste quebra em vez de passar por sorte.
    """

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


def como_aluno(monkeypatch):
    dublar(monkeypatch, sessao=SESSAO_DA_ANA, categoria="aluno")


def como_cadastrado(monkeypatch):
    """Tem login, NÃO comprou. A categoria 2 da lei das categorias."""
    dublar(monkeypatch, sessao=SESSAO_DA_ANA, categoria="cadastrado")


def sem_login(monkeypatch):
    dublar(monkeypatch, sessao={"autenticado": False})


@pytest.fixture
def sala():
    """A área onde o aluno escreve: trancada para o mundo, aberta para a turma."""
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


def conversa(area) -> Topico:
    autor = Pessoa.objects.create(
        id_da_plataforma="p_prof", email="prof@exemplo.com", nome_exibido="Professor"
    )
    topico = Topico.objects.create(area=area, autor=autor, titulo="Uma conversa")
    Mensagem.objects.create(topico=topico, autor=autor, texto="a primeira fala")
    return topico


def abrir(client, area, **extra):
    return client.post(
        reverse("novo_topico", args=[area.slug]),
        {"titulo": "Como faço a textura não esticar?", "texto": "Travei no Studio."},
        headers={"cookie": COOKIE},
        **extra,
    )


def responder(client, topico, **extra):
    return client.post(
        reverse("responder", args=[topico.pk]),
        {"texto": "Tenta escalar o UV antes de exportar."},
        headers={"cookie": COOKIE},
        **extra,
    )


# ======================================================================
# 1. O ALUNO MATRICULADO ESCREVE — o caso que a tarefa existe para entregar
# ======================================================================
def test_aluno_matriculado_abre_topico_e_responde(client, env, monkeypatch, sala):
    como_aluno(monkeypatch)

    resposta = abrir(client, sala)
    assert resposta.status_code == 302, resposta.content[:400]
    topico = Topico.objects.get()
    assert topico.titulo == "Como faço a textura não esticar?"
    assert topico.area_id == sala.pk
    assert topico.autor.email == "ana@exemplo.com"
    # A proteção é o CADEADO, não a fila de aprovação: nasce publicado.
    assert topico.estado == Topico.Estado.PUBLICADO
    assert topico.mensagens.count() == 1
    assert topico.mensagens.get().texto == "Travei no Studio."
    # E o destino leva à âncora da mensagem recém-escrita, não ao topo.
    assert resposta["Location"].endswith(f"#m{topico.mensagens.get().pk}")

    assert responder(client, topico).status_code == 302
    assert topico.mensagens.count() == 2


def test_a_mensagem_nasce_com_a_coluna_de_busca_preenchida(
    client, env, monkeypatch, sala
):
    """Lei §4.4: a busca é calculada na ESCRITA, nunca no `WHERE` da consulta.

    Com 500 mensagens as duas formas são indistinguíveis; com 50 mil, uma delas
    trava — e isso só se descobre em produção. O guarda tem de morar no caminho
    de escrita, que é onde a coluna é preenchida.
    """
    from django.contrib.postgres.search import SearchQuery

    como_aluno(monkeypatch)
    abrir(client, sala)

    achadas = Mensagem.objects.filter(busca=SearchQuery("travar", config="portuguese"))
    assert achadas.count() == 1, (
        "a mensagem entrou com a coluna `busca` vazia — a busca em português "
        "não a encontra, e ninguém repara até o fórum crescer"
    )


def test_responder_avanca_a_ultima_atividade_do_topico(client, env, monkeypatch, sala):
    """A marca de leitura compara com `ultima_atividade_em` (`MarcaDeLeitura`).

    Sem este avanço, uma conversa que acabou de receber resposta continuaria
    parecendo lida para a turma inteira.
    """
    como_aluno(monkeypatch)
    topico = conversa(sala)
    antes = topico.ultima_atividade_em

    responder(client, topico)

    topico.refresh_from_db()
    assert topico.ultima_atividade_em > antes


# ======================================================================
# 2. AS DUAS PROVAS NEGATIVAS — quem NÃO escreve
# ======================================================================
def test_quem_tem_cadastro_sem_matricula_e_recusado(client, env, monkeypatch, sala):
    """*"Quem paga escreve; quem só tem cadastro lê."* — a escolha dele.

    É o desenho de anti-spam do fórum: para estragá-lo, a pessoa teria que
    pagar o curso.
    """
    como_cadastrado(monkeypatch)
    topico = conversa(sala)

    # A área é de ALUNOS, então quem só tem cadastro nem enxerga: 404, e não
    # 403 — um 403 confirmaria que a área existe.
    assert abrir(client, sala).status_code == 404
    assert responder(client, topico).status_code == 404
    assert Topico.objects.count() == 1
    assert Mensagem.objects.count() == 1


def test_quem_tem_cadastro_nao_escreve_nem_onde_consegue_ler(
    client, env, monkeypatch, avisos
):
    """A prova que o 404 acima não dá: aqui ele LÊ, e mesmo assim não escreve.

    Sem este caso, "recusado" poderia ser só efeito de não enxergar a área — e
    a regra de quem escreve continuaria sem guarda nenhum.
    """
    como_cadastrado(monkeypatch)
    topico = conversa(avisos)

    assert client.get(reverse("area", args=[avisos.slug])).status_code == 200
    assert abrir(client, avisos).status_code == 403
    assert responder(client, topico).status_code == 403
    assert Mensagem.objects.count() == 1


def test_quem_nao_tem_login_e_recusado(client, env, monkeypatch, avisos):
    """Visitante lê a área pública e não escreve nela. Nem com POST na mão."""
    sem_login(monkeypatch)
    topico = conversa(avisos)

    assert client.get(reverse("area", args=[avisos.slug])).status_code == 200
    assert abrir(client, avisos).status_code == 403
    assert responder(client, topico).status_code == 403
    assert Mensagem.objects.count() == 1


def test_visitante_sem_cookie_nenhum_tambem_e_recusado(client, avisos):
    """Sem cookie o fórum nem chega a perguntar quem é — e continua fechado.

    Sem a fixture `env` e sem dublê de propósito: se este caminho tocasse a
    rede, o corte do `conftest` quebraria o teste.
    """
    topico = conversa(avisos)
    assert (
        client.post(
            reverse("novo_topico", args=[avisos.slug]),
            {"titulo": "quero postar", "texto": "sem entrar"},
        ).status_code
        == 403
    )
    assert (
        client.post(reverse("responder", args=[topico.pk]), {"texto": "x"}).status_code
        == 403
    )
    assert Mensagem.objects.count() == 1


# ======================================================================
# 3. EM PÁGINA PÚBLICA, SÓ A ESCOLA FALA
# ======================================================================
def test_nem_o_aluno_escreve_na_area_publica(client, env, monkeypatch, avisos):
    """O coração do mandato 1: menor de idade não escreve em página pública.

    A área é aberta ao Google e a estranhos; quem publica nela é a escola. Um
    aluno matriculado — que escreve em toda área de aluno — é recusado AQUI.
    """
    como_aluno(monkeypatch)
    topico = conversa(avisos)

    assert abrir(client, avisos).status_code == 403
    assert responder(client, topico).status_code == 403
    assert Mensagem.objects.count() == 1


def test_o_banco_recusa_area_publica_onde_aluno_escreve():
    """O cadeado abaixo do código: a combinação proibida não chega a existir.

    A permissão também confere, e é ela que decide cada requisição. Mas regra
    que só existe em código é promessa: bastaria um `update()` numa tela de
    administração futura, ou uma linha editada à mão no `psql` numa madrugada
    de incidente. Aqui o PostgreSQL recusa.
    """
    for quem_escreve in [Area.QuemEscreve.ALUNO, Area.QuemEscreve.CADASTRADO]:
        with pytest.raises(IntegrityError), transaction.atomic():
            Area.objects.create(
                slug=f"proibida-{quem_escreve}",
                nome="Não deveria existir",
                visibilidade=Area.Visibilidade.PUBLICA,
                quem_escreve=quem_escreve,
            )


def test_o_banco_recusa_ate_pelo_update_que_fura_o_save():
    """`QuerySet.update()` fura guarda escrito em `Model.save()` (`armadilhas/023`).

    Este é o caminho pelo qual a área pública voltaria a aceitar aluno sem
    ninguém notar — e é justamente o que a restrição do banco alcança.
    """
    area = Area.objects.create(
        slug="avisos", nome="Avisos", visibilidade=Area.Visibilidade.PUBLICA
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Area.objects.filter(pk=area.pk).update(quem_escreve="aluno")


def test_area_nasce_fechada_quando_ninguem_diz_quem_escreve():
    """O default é o lado FECHADO: quem escreve, por omissão, é a escola."""
    area = Area.objects.create(slug="nova", nome="Nova")
    assert area.quem_escreve == Area.QuemEscreve.EQUIPE


# ======================================================================
# 4. A PORTA EM SI — método, CSRF e conversa trancada
# ======================================================================
def test_escrever_por_GET_nao_existe(client, env, monkeypatch, sala):
    """Escrita por GET é escrita que um `<img src>` de outro site dispara."""
    como_aluno(monkeypatch)
    topico = conversa(sala)
    assert (
        client.get(
            reverse("novo_topico", args=[sala.slug]), headers={"cookie": COOKIE}
        ).status_code
        == 405
    )
    assert (
        client.get(
            reverse("responder", args=[topico.pk]), headers={"cookie": COOKIE}
        ).status_code
        == 405
    )


def test_o_formulario_da_tela_atravessa_a_conferencia_de_CSRF(env, monkeypatch, sala):
    """**Prova de fora do formulário, com o CSRF LIGADO.**

    Os outros testes rodam com o cliente padrão, que dispensa o token — eles
    provam a permissão, não a página. Este monta o fluxo inteiro: pede a tela,
    lê o token que ela imprimiu e o devolve no POST.

    Por que ele importa nesta célula: o fórum **não assina sessão** (lei §3), e
    a forma óbvia de guardar o token de CSRF no Django é `CSRF_USE_SESSIONS`.
    Se alguém ligar isso um dia, o formulário quebra em produção e só lá — aqui
    ele fica vermelho antes.
    """
    como_aluno(monkeypatch)
    navegador = Client(enforce_csrf_checks=True)
    # O crachá vai no POTE de cookies do cliente, e não num cabeçalho `cookie`
    # explícito — um cabeçalho cru SUBSTITUI o pote inteiro, e junto com ele o
    # `forum_csrf` que a tela acabou de plantar. O navegador de verdade manda
    # os dois na mesma linha; este teste tem de fazer igual.
    navegador.cookies["meshcraft_sessao"] = "um-cookie-opaco-qualquer"

    sem_token = navegador.post(
        reverse("novo_topico", args=[sala.slug]),
        {"titulo": "sem token nenhum", "texto": "não deveria entrar"},
    )
    assert sem_token.status_code == 403
    assert Topico.objects.count() == 0

    tela = navegador.get(reverse("area", args=[sala.slug]))
    assert tela.status_code == 200
    corpo = tela.content.decode()
    assert "csrfmiddlewaretoken" in corpo, "a tela não imprimiu o formulário"

    marca = 'name="csrfmiddlewaretoken" value="'
    token = corpo.split(marca, 1)[1].split('"', 1)[0]
    com_token = navegador.post(
        reverse("novo_topico", args=[sala.slug]),
        {
            "titulo": "Agora vai, com o token da própria tela",
            "texto": "o formulário de verdade",
            "csrfmiddlewaretoken": token,
        },
    )
    assert com_token.status_code == 302, com_token.content[:400]
    assert Topico.objects.count() == 1


def test_conversa_trancada_recusa_resposta(client, env, monkeypatch, sala):
    """Trancar é da moderação (lei §4.6) e vale na porta, não só na tela."""
    como_aluno(monkeypatch)
    topico = conversa(sala)
    Topico.objects.filter(pk=topico.pk).update(trancado=True)
    topico.refresh_from_db()

    assert responder(client, topico).status_code == 403
    assert Mensagem.objects.count() == 1


def test_topico_esperando_moderacao_nao_aceita_resposta(client, env, monkeypatch, sala):
    """O estado `esperando` some da leitura — e a porta de escrita concorda."""
    como_aluno(monkeypatch)
    topico = conversa(sala)
    Topico.objects.filter(pk=topico.pk).update(estado=Topico.Estado.ESPERANDO)
    topico.refresh_from_db()

    assert responder(client, topico).status_code == 404


# ======================================================================
# 5. QUANDO A PESSOA ERRA — a tela recusa sem perder o que ela digitou
# ======================================================================
def test_titulo_curto_devolve_a_tela_com_o_texto_ainda_dentro(
    client, env, monkeypatch, sala
):
    """Esta célula não tem sessão, logo não tem `messages` para levar recado.

    Recusar por redirect perderia o que a pessoa escreveu — a pior forma de
    dizer não para quem acabou de digitar seis linhas.
    """
    como_aluno(monkeypatch)
    resposta = client.post(
        reverse("novo_topico", args=[sala.slug]),
        {"titulo": "oi", "texto": "um texto longo que eu não quero perder"},
        headers={"cookie": COOKIE},
    )
    assert resposta.status_code == 400
    corpo = resposta.content.decode()
    assert "pelo menos 5 letras" in corpo
    assert "um texto longo que eu não quero perder" in corpo
    assert Topico.objects.count() == 0


def test_mensagem_vazia_nao_entra(client, env, monkeypatch, sala):
    como_aluno(monkeypatch)
    topico = conversa(sala)
    resposta = client.post(
        reverse("responder", args=[topico.pk]),
        {"texto": "   \n  "},
        headers={"cookie": COOKIE},
    )
    assert resposta.status_code == 400
    assert Mensagem.objects.count() == 1


def test_texto_gigante_e_recusado_antes_do_banco(client, env, monkeypatch, sala):
    """Sem este teto, um `DataError` do PostgreSQL viraria HTTP 500 na cara."""
    como_aluno(monkeypatch)
    resposta = client.post(
        reverse("novo_topico", args=[sala.slug]),
        {"titulo": "Um título aceitável", "texto": "a" * 20001},
        headers={"cookie": COOKIE},
    )
    assert resposta.status_code == 400
    assert Topico.objects.count() == 0


# ======================================================================
# 6. A TELA DIZ POR QUÊ — recusa em silêncio parece site quebrado
# ======================================================================
def test_a_tela_convida_a_entrar_quem_nao_esta_logado(client, env, monkeypatch, avisos):
    sem_login(monkeypatch)
    corpo = client.get(
        reverse("area", args=[avisos.slug]), headers={"cookie": COOKIE}
    ).content.decode()
    assert "Entre para escrever aqui." in corpo
    # E o convite volta PARA CÁ depois de entrar.
    assert "/entrar/google?next=" in corpo
    assert "csrfmiddlewaretoken" not in corpo


def test_a_tela_explica_a_matricula_para_quem_so_tem_cadastro(
    client, env, monkeypatch, avisos
):
    """Aqui ele lê, e a página diz por que não escreve — em português."""
    como_cadastrado(monkeypatch)
    corpo = client.get(
        reverse("area", args=[avisos.slug]), headers={"cookie": COOKIE}
    ).content.decode()
    assert "quem publica é a escola" in corpo
    assert "csrfmiddlewaretoken" not in corpo


def test_o_aluno_ve_o_formulario_na_area_dele(client, env, monkeypatch, sala):
    como_aluno(monkeypatch)
    corpo = client.get(
        reverse("area", args=[sala.slug]), headers={"cookie": COOKIE}
    ).content.decode()
    assert "Abrir uma conversa" in corpo
    assert reverse("novo_topico", args=[sala.slug]) in corpo
