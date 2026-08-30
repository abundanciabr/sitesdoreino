"""Guardas da BUSCA — e as duas que existem para impedir um acidente, não um bug.

A tela de busca é a única do fórum que atravessa TODAS as áreas de uma vez. As
duas coisas que ela não pode fazer, e que esta suíte trava:

1. **Vazar o que a pessoa não poderia ler.** Um visitante que digita a palavra
   certa não pode receber, no resultado, a mensagem de um aluno numa área
   privada. Quem decide é `areas_visiveis`, a mesma função das telas.
2. **Publicar o texto do aluno como HTML.** O `ts_headline` do PostgreSQL não
   escapa o texto de origem; sem o cuidado de `apps/core/busca.py`, uma
   mensagem com `<script>` viraria script rodando na tela de quem busca.

**Tudo aqui atravessa a porta pela rede**, como no resto da célula: monta-se o
mundo, dubla-se a `identidade` e a `alunos`, e pede-se a URL como um navegador
pediria. E **contra um PostgreSQL de verdade** — com dublê de banco, uma
afirmação errada sobre a busca entra no repositório como se fosse verdade
(`armadilhas/154`).
"""

from __future__ import annotations

import httpx
import pytest
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
SESSAO_DO_DONO = {
    "autenticado": True,
    "id": "p_dono",
    "email": "dono@exemplo.com",
    "nome_exibido": "Davi",
}


@pytest.fixture
def env(monkeypatch):
    for nome, valor in [
        ("IDENTIDADE_API_URL", "http://identidade:8000/interno"),
        ("IDENTIDADE_API_TOKEN", "tok-id"),
        ("ALUNOS_API_URL", "http://alunos:8000/api/alunos"),
        ("ALUNOS_API_TOKEN", "tok-al"),
        ("FORUM_PROFESSORES", ""),
        ("ADMIN_EMAILS", "dono@exemplo.com"),
    ]:
        monkeypatch.setenv(nome, valor)


def dublar(monkeypatch, *, sessao=None, categoria=None):
    def falso_get(self, url, **kwargs):
        if "identidade" in str(url):
            if sessao is None:
                raise AssertionError("chamada inesperada à identidade")
            return httpx.Response(200, json=sessao)
        if categoria is None:
            raise AssertionError("chamada inesperada à alunos")
        return httpx.Response(200, json={"categoria": categoria})

    monkeypatch.setattr(httpx.Client, "get", falso_get)


def como_aluna(monkeypatch):
    dublar(monkeypatch, sessao=SESSAO_DA_ANA, categoria="aluno")


def como_dono(monkeypatch):
    dublar(monkeypatch, sessao=SESSAO_DO_DONO, categoria="cadastrado")


def sem_login(monkeypatch):
    dublar(monkeypatch, sessao={"autenticado": False})


def procurar(client, termo, **extra):
    return client.get(
        reverse("buscar"), {"q": termo, **extra}, headers={"cookie": COOKIE}
    )


@pytest.fixture
def escola():
    """As duas áreas que o fórum tem de verdade: uma aberta, uma trancada."""
    return {
        "avisos": Area.objects.create(
            slug="avisos",
            nome="Avisos da escola",
            visibilidade=Area.Visibilidade.PUBLICA,
            quem_escreve=Area.QuemEscreve.EQUIPE,
        ),
        "duvidas": Area.objects.create(
            slug="duvidas",
            nome="Dúvidas gerais",
            visibilidade=Area.Visibilidade.ALUNOS,
            quem_escreve=Area.QuemEscreve.ALUNO,
        ),
    }


@pytest.fixture
def ana():
    return Pessoa.objects.create(
        id_da_plataforma="p_ana", email="ana@exemplo.com", nome_exibido="Ana"
    )


def falar(area, autora, titulo, texto, **campos) -> Mensagem:
    """Uma conversa com uma fala, já indexada — como a escrita real faz.

    `autora=None` significa que quem publicou foi a ESCOLA, e aí a declaração
    é obrigatória: o banco recusa fala sem pessoa e sem o selo da instituição
    (`_fala_de_pessoa_ou_da_escola`). Não é detalhe de teste — é a restrição
    que impede uma mensagem ganhar autor de aluno por acidente.
    """
    da_escola = autora is None
    topico = Topico.objects.create(
        area=area, autor=autora, publicado_pela_escola=da_escola, titulo=titulo
    )
    mensagem = Mensagem.objects.create(
        topico=topico,
        autor=autora,
        publicado_pela_escola=da_escola,
        texto=texto,
        **campos,
    )
    mensagem.indexar_para_busca()
    return mensagem


# ======================================================================
# 1. AS DUAS QUE EXISTEM PARA IMPEDIR UM ACIDENTE
# ======================================================================
def test_a_busca_nao_entrega_area_privada_para_quem_nao_pode_ler(
    client, env, monkeypatch, escola, ana
):
    """O pior acidente possível num fórum de escola, travado.

    A mesma palavra existe nas duas áreas. O visitante só pode receber a da
    área aberta; a da área trancada não pode nem aparecer, nem em trecho.
    """
    falar(
        escola["avisos"], None, "Aviso sobre textura", "A aula de textura mudou de dia."
    )
    escondida = falar(
        escola["duvidas"], ana, "Minha textura estica", "A textura do braço estica."
    )
    Topico.objects.filter(pk=escondida.topico_id).update(publicado_pela_escola=False)

    # O que se procura no HTML é um pedaço que o destaque NÃO parte no meio: a
    # palavra que casou vem embrulhada em `<mark>`, então "A aula de textura"
    # não existe como texto contínuo na página.
    sem_login(monkeypatch)
    pagina = procurar(client, "textura").content.decode()
    assert "mudou de dia" in pagina
    assert "estica" not in pagina, (
        "a busca entregou a mensagem de uma aluna numa área trancada para quem "
        "nem tem login: é o vazamento que esta suíte existe para impedir"
    )

    # E para quem PODE ler, as duas aparecem.
    como_aluna(monkeypatch)
    pagina = procurar(client, "textura").content.decode()
    assert "mudou de dia" in pagina
    assert "estica" in pagina


def test_o_destaque_nao_publica_o_html_que_o_aluno_escreveu(
    client, env, monkeypatch, escola, ana
):
    """A carga desta prova foi ESCOLHIDA POR MEDIÇÃO, e a escolha é o teste.

    Contra um PostgreSQL 17 de verdade, `ts_headline` **remove** um
    `<script>...</script>` (o parser dele reconhece a tag e a descarta), mas
    devolve `<img src=x onerror=alert(1)>` **inteiro** — provavelmente por não
    reconhecê-lo como tag válida. Um teste escrito com `<script>` passaria
    mesmo sem escape nenhum, e daria a impressão de que a tela é segura.

    Por isso a prova usa a carga que sobrevive: é ela que separa "o Postgres
    limpou" de "o nosso código escapou".
    """
    falar(
        escola["duvidas"],
        ana,
        "Uma dúvida com armadilha",
        "<img src=x onerror=alert(1)> como faço a textura?",
    )

    como_aluna(monkeypatch)
    pagina = procurar(client, "textura").content.decode()

    assert "<img" not in pagina, (
        "o texto do aluno saiu como HTML de verdade: quem buscasse esta palavra "
        "executaria o que ele escreveu"
    )
    assert (
        "&lt;img src=x onerror=alert(1)&gt;" in pagina
    ), "o trecho tem de aparecer escapado e visível, não sumir"
    # E o destaque continua funcionando na mesma resposta.
    assert "<mark>" in pagina


def test_um_marcador_forjado_na_mensagem_nao_vira_outra_tag(
    client, env, monkeypatch, escola, ana
):
    """Quem escrever o marcador interno na mensagem consegue, no máximo, um
    destaque a mais. Nunca outra tag: depois do escape, o ÚNICO texto que ainda
    pode virar HTML é o marcador, e ele só sabe virar `<mark>`."""
    falar(
        escola["duvidas"],
        ana,
        "Marcador forjado",
        "[[hl]]textura[[/hl]] e um <img src=x onerror=alert(1)> junto",
    )

    como_aluna(monkeypatch)
    trecho = procurar(client, "textura").content.decode().split('class="texto"')[1]
    trecho = trecho.split("</div>")[0]

    assert "<img" not in trecho
    assert "&lt;img" in trecho
    # Sobrou um destaque a mais, e é só isso que o forjador consegue.
    assert trecho.count("<mark>") == trecho.count("</mark>")


# ======================================================================
# 2. A BUSCA FAZENDO O QUE FOI PEDIDA PARA FAZER
# ======================================================================
def test_acha_a_mensagem_e_leva_direto_para_ela(client, env, monkeypatch, escola, ana):
    mensagem = falar(
        escola["duvidas"],
        ana,
        "A textura estica no braço",
        "Travei na hora de exportar o modelo para o Studio.",
    )
    como_aluna(monkeypatch)

    pagina = procurar(client, "exportar").content.decode()
    endereco = reverse("topico", args=[mensagem.topico_id])
    assert (
        f'href="{endereco}#m{mensagem.pk}"' in pagina
    ), "o resultado tem de levar à MENSAGEM dentro da conversa, não ao topo"
    assert "A textura estica no braço" in pagina
    assert "1 resultado" in pagina


def test_destaca_o_que_casou(client, env, monkeypatch, escola, ana):
    falar(escola["duvidas"], ana, "Uma dúvida", "O Studio trava ao exportar o modelo.")
    como_aluna(monkeypatch)

    pagina = procurar(client, "exportar").content.decode()
    assert "<mark>" in pagina and "</mark>" in pagina


def test_a_caixa_de_busca_aparece_em_todas_as_telas(client, env, monkeypatch, escola):
    """Procurar é o gesto que a pessoa faz de qualquer lugar. Se a caixa
    morasse só na capa, ela não existiria no meio de uma conversa, que é
    justamente onde a dúvida aparece."""
    sem_login(monkeypatch)
    endereco = reverse("buscar")

    capa = client.get(reverse("home"), headers={"cookie": COOKIE})
    area = client.get(reverse("area", args=["avisos"]), headers={"cookie": COOKIE})
    for resposta in (capa, area):
        assert resposta.status_code == 200
        assert f'action="{endereco}"' in resposta.content.decode()


def test_sem_termo_a_tela_convida_em_vez_de_errar(client, env, monkeypatch, escola):
    sem_login(monkeypatch)
    resposta = client.get(reverse("buscar"), headers={"cookie": COOKIE})
    assert resposta.status_code == 200
    assert "Procurar no fórum" in resposta.content.decode()


def test_termo_de_uma_letra_e_recusado_com_explicacao(
    client, env, monkeypatch, escola, ana
):
    falar(escola["duvidas"], ana, "Uma dúvida", "O Studio trava ao exportar.")
    como_aluna(monkeypatch)

    pagina = procurar(client, "a").content.decode()
    assert "Escreva um pouco mais" in pagina
    assert "Studio" not in pagina


def test_pontuacao_solta_nao_derruba_a_pagina(client, env, monkeypatch, escola, ana):
    """A caixa aceita o que qualquer pessoa digitar. `websearch_to_tsquery` é o
    que garante que aspas soltas e sinais não viram erro de banco."""
    falar(escola["duvidas"], ana, "Uma dúvida", "O Studio trava ao exportar.")
    como_aluna(monkeypatch)

    for esquisito in ['"', "& | !", "-", "'aspas soltas", "a & b )"]:
        assert procurar(client, esquisito).status_code == 200, esquisito


def test_nada_encontrado_explica_o_acento(client, env, monkeypatch, escola, ana):
    """O limite medido em `armadilhas/154`: a busca é sensível a acento, e no
    Brasil quase ninguém acentua ao buscar. A tela diz isso em vez de deixar a
    pessoa concluir que a resposta não existe."""
    falar(escola["duvidas"], ana, "Uma dúvida", "Meu chapéu ficou torto.")
    como_aluna(monkeypatch)

    pagina = procurar(client, "chapeu").content.decode()
    assert "Nada encontrado" in pagina
    assert "acento" in pagina


def test_com_a_cura_instalada_a_busca_acha_sem_acento(
    client, env, monkeypatch, escola, ana
):
    """A cura de `armadilhas/154`, provada pela TELA e não só pelo modelo.

    Com a configuração sem acento ativa, quem digita `chapeu` acha `chapéu` — e
    o aviso sobre acento some da tela, porque ele é calculado do que está ativo
    (`acento_importa`), não escrito à mão.

    O `setenv` vem ANTES de escrever a mensagem de propósito: a indexação
    acontece na escrita, e indexar com uma configuração para procurar com outra
    é justamente o defeito que este desenho evita.
    """
    from apps.forum.config_de_busca import CONFIG_SEM_ACENTO

    monkeypatch.setenv("FORUM_BUSCA_CONFIG", CONFIG_SEM_ACENTO)
    falar(escola["duvidas"], ana, "Uma dúvida", "Meu chapéu ficou torto.")
    como_aluna(monkeypatch)

    pagina = procurar(client, "chapeu").content.decode()
    assert "1 resultado" in pagina, "com a cura instalada, sem acento tem de achar"
    assert "ficou torto" in pagina
    # E quem escreve certo continua achando.
    assert "1 resultado" in procurar(client, "chapéu").content.decode()


def test_sem_a_cura_a_tela_avisa_e_com_a_cura_ela_cala(
    client, env, monkeypatch, escola, ana
):
    """O aviso do acento é MEDIDO, não lembrado.

    Sem esta prova, a frase sobre acento continuaria na tela para sempre depois
    da cura — e uma tela que ensina um limite que não existe mais é pior do que
    uma tela calada.
    """
    from apps.forum.config_de_busca import CONFIG_SEM_ACENTO

    falar(escola["duvidas"], ana, "Uma dúvida", "Meu chapéu ficou torto.")
    como_aluna(monkeypatch)
    assert "acento" in procurar(client, "girafa").content.decode()

    monkeypatch.setenv("FORUM_BUSCA_CONFIG", CONFIG_SEM_ACENTO)
    assert "acento" not in procurar(client, "girafa").content.decode()


# ======================================================================
# 3. O QUE ESTÁ FORA DO AR SEGUE FORA DO AR — inclusive aqui
# ======================================================================
def test_mensagem_fora_do_ar_some_da_busca_da_aluna_e_fica_na_do_dono(
    client, env, monkeypatch, escola, ana
):
    from django.utils import timezone

    mensagem = falar(
        escola["duvidas"], ana, "Uma dúvida", "O Studio trava ao exportar o modelo."
    )
    Mensagem.objects.filter(pk=mensagem.pk).update(removida_em=timezone.now())

    como_aluna(monkeypatch)
    assert "Studio" not in procurar(client, "exportar").content.decode()

    como_dono(monkeypatch)
    pagina = procurar(client, "exportar").content.decode()
    assert "Studio" in pagina
    assert "fora do ar" in pagina


def test_conversa_fora_do_ar_some_da_busca_da_aluna(
    client, env, monkeypatch, escola, ana
):
    mensagem = falar(
        escola["duvidas"], ana, "Uma dúvida", "O Studio trava ao exportar o modelo."
    )
    Topico.objects.filter(pk=mensagem.topico_id).update(estado=Topico.Estado.REMOVIDO)

    como_aluna(monkeypatch)
    assert "Studio" not in procurar(client, "exportar").content.decode()

    como_dono(monkeypatch)
    assert "Studio" in procurar(client, "exportar").content.decode()


def test_area_arquivada_some_da_busca_de_quem_nao_modera(
    client, env, monkeypatch, escola, ana
):
    """A mesma regra de `pode_ler`: arquivada é indistinguível de inexistente,
    menos para quem pode reabri-la."""
    falar(escola["duvidas"], ana, "Uma dúvida", "O Studio trava ao exportar.")
    Area.objects.filter(pk=escola["duvidas"].pk).update(ativa=False)

    como_aluna(monkeypatch)
    assert "Studio" not in procurar(client, "exportar").content.decode()

    como_dono(monkeypatch)
    assert "Studio" in procurar(client, "exportar").content.decode()


# ======================================================================
# 4. MUITOS RESULTADOS
# ======================================================================
def test_a_lista_se_divide_em_paginas(client, env, monkeypatch, escola, ana):
    for numero in range(25):
        falar(
            escola["duvidas"],
            ana,
            f"Dúvida número {numero}",
            f"O Studio trava ao exportar o modelo {numero}.",
        )
    como_aluna(monkeypatch)

    primeira = procurar(client, "exportar").content.decode()
    assert "25 resultados" in primeira
    assert "página 1 de 2" in primeira
    assert "próximas" in primeira

    segunda = procurar(client, "exportar", p=2).content.decode()
    assert "página 2 de 2" in segunda
    assert "anteriores" in segunda
