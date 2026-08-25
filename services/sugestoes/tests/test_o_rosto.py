"""O ROSTO da Caixa (EVO-30), medido pela borda HTTP — nunca pelo contexto.

O que este arquivo prova é o que o aluno passa a CONSEGUIR FAZER: abrir o
quadro, trocar de aba, votar e desvotar clicando, ler a história de uma ideia e
mandar a sua depois de conferir se já existe. Toda asserção olha o HTML que o
navegador receberia ou o efeito no banco — nenhuma espia `response.context`,
que continuaria verde no dia em que o template parasse de mostrar a variável.

Duas amarras deste arquivo merecem leitura antes de mexer nele:

* **o voto é disparado pelo `action` que está NA PÁGINA**, extraído do HTML por
  regex. Um teste que chamasse `reverse("votar")` provaria que a view funciona
  e continuaria verde com o botão fora da tela — que é exatamente a falha que
  este despacho existe para não cometer;
* **o CSS é medido sob `SCRIPT_NAME`**, que é o único regime em que a diferença
  entre `{% static %}` e `{% url 'estatico' %}` aparece. Sem o prefixo ligado,
  os dois devolvem `/static/…` e o guarda ficaria verde para sempre
  (armadilhas/029, /081 e /083; a lição inteira em `armadilhas/102`).
"""

import re

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient
from django.urls import clear_script_prefix, reverse, set_script_prefix

from apps.sugestoes.models import Sugestao, Voto

pytestmark = pytest.mark.django_db

PREFIXO = "/forms/sugestoes"

# O voto, como ele chega ao navegador: para onde o botão aponta e o que ele diz.
# São dois padrões e não um só porque a página tem OUTROS formulários (o de sair,
# o de comentar) — um `.*?` do primeiro `<form>` até o primeiro `title=` pegaria
# o botão errado, e o teste mediria o link do trilho achando que media o voto.
ACAO_DO_VOTO = re.compile(r'action="([^"]*/(?:des)?votar)"')
ROTULO_DO_VOTO = re.compile(r'class="voto[^"]*"\s+title="([^"]*)"')
CONTAGEM = re.compile(r'<span class="votos">(\d+)</span>')
TITULO_DE_PECA = re.compile(r'<h3 class="peca-titulo"><a href="[^"]*">([^<]+)</a>')


def _quadro(pessoa, **query) -> str:
    endereco = reverse("quadro")
    if query:
        endereco += "?" + "&".join(f"{c}={v}" for c, v in query.items())
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


# ---------------------------------------------------------------------------
# O quadro: a grade, as duas abas, e o que NÃO está aqui
# ---------------------------------------------------------------------------


def test_o_quadro_abre_para_o_aluno_logado_e_desenha_a_grade(caixa):
    caixa.publicar("Legendas nas aulas")

    corpo = _quadro(caixa.aluno)

    assert 'class="grade"' in corpo, "o quadro não desenhou a grade de peças"
    assert TITULO_DE_PECA.findall(corpo) == ["Legendas nas aulas"]
    # A folha de estilo é do rosto: sem ela a grade vira uma lista de texto.
    assert 'rel="stylesheet"' in corpo


def test_as_abas_sao_duas_e_em_alta_nao_e_uma_delas(caixa):
    """ "Em alta" é V1.2 (PLANO-MESTRE §6) — desenhá-la agora seria prometer
    uma ordenação por recência que ninguém decidiu como calcular."""
    corpo = _quadro(caixa.aluno)

    assert "Mais votadas" in corpo
    assert "Novas" in corpo
    assert "Em alta" not in corpo


def test_a_aba_novas_ordena_pela_chegada_e_a_padrao_pelos_votos(caixa, entrar_como):
    """As duas abas mostram as MESMAS sugestões em ordens diferentes."""
    primeira = caixa.publicar("Chegou primeiro")
    caixa.publicar("Chegou depois")
    quem_vota = entrar_como("votante@exemplo.test", "Votante")
    assert caixa.votar(primeira, quem=quem_vota).status_code == 302

    mais_votadas = TITULO_DE_PECA.findall(_quadro(caixa.aluno))
    novas = TITULO_DE_PECA.findall(_quadro(caixa.aluno, ordem="novas"))

    assert mais_votadas == ["Chegou primeiro", "Chegou depois"]
    assert novas == ["Chegou depois", "Chegou primeiro"]


def test_uma_aba_inventada_para_a_pagina_em_vez_de_escolher_por_conta(caixa):
    """Fail-closed, como a categoria inexistente já era: servir a ordem padrão
    faria a aba mentir — a pessoa pediria uma coisa e receberia outra."""
    assert (
        caixa.aluno.client.get(f"{reverse('quadro')}?ordem=em-alta").status_code == 404
    )


def test_a_aba_carrega_o_filtro_e_o_filtro_carrega_a_aba(caixa):
    """Trocar de aba não pode apagar a categoria escolhida, nem o contrário —
    senão cada clique desfaz metade da escolha anterior."""
    caixa.publicar("Legendas nas aulas")

    corpo = _quadro(caixa.aluno, ordem="novas", categoria="curso")

    assert f'href="{reverse("quadro")}?ordem=novas&amp;categoria=curso"' in corpo
    assert f'href="{reverse("quadro")}?ordem=mais-votadas&amp;categoria=curso"' in corpo


# ---------------------------------------------------------------------------
# O voto, clicando no que está na tela
# ---------------------------------------------------------------------------


def _clicar_no_voto(pessoa, corpo: str):
    """Segue o `action` do formulário que a página realmente entregou."""
    enderecos = ACAO_DO_VOTO.findall(corpo)
    rotulos = ROTULO_DO_VOTO.findall(corpo)
    assert enderecos and rotulos, "a página não trouxe nenhum botão de voto"
    endereco, rotulo = enderecos[0], rotulos[0]
    resposta = pessoa.client.post(endereco, {"de": "quadro"})
    assert resposta.status_code == 302, resposta.status_code
    return rotulo


def test_votar_e_desvotar_pela_tela_mudam_a_contagem_que_a_pessoa_ve(caixa):
    sugestao = caixa.publicar("Legendas nas aulas")

    antes = _quadro(caixa.aluno)
    assert CONTAGEM.findall(antes) == ["0"]
    assert _clicar_no_voto(caixa.aluno, antes) == "Votar"

    depois = _quadro(caixa.aluno)
    assert CONTAGEM.findall(depois) == ["1"]
    assert Voto.objects.filter(sugestao=sugestao).count() == 1
    assert _clicar_no_voto(caixa.aluno, depois) == "Tirar meu voto"

    de_volta = _quadro(caixa.aluno)
    assert CONTAGEM.findall(de_volta) == ["0"]
    assert Voto.objects.filter(sugestao=sugestao).count() == 0


# ---------------------------------------------------------------------------
# O detalhe: a conversa e a história da ideia
# ---------------------------------------------------------------------------


def test_a_pagina_da_sugestao_conta_por_onde_a_ideia_andou(caixa):
    sugestao = caixa.publicar("Legendas nas aulas")
    assert (
        caixa.mudar_status(
            sugestao, Sugestao.Status.PLANEJADO, nota="Entra no ciclo de setembro."
        ).status_code
        == 302
    )

    corpo = caixa.aluno.client.get(
        reverse("sugestao", args=[sugestao.id])
    ).content.decode()

    assert 'class="etapas"' in corpo, "a linha do tempo não foi desenhada"
    assert "Em desenvolvimento" in corpo  # a etapa existe mesmo sem ter chegado nela
    assert "Entra no ciclo de setembro." in corpo


def test_a_historia_mostra_a_decisao_e_nunca_quem_decidiu(caixa):
    """O `HistoricoStatus` é a auditoria da EQUIPE: `alterado_por` é uma
    `Identidade`, com e-mail dentro. O recorte é feito na CONSULTA
    (`.values(...)`), então não há o que um `{{ … }}` distraído alcançar."""
    sugestao = caixa.publicar("Legendas nas aulas")
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="Vale a pena.")

    corpo = caixa.aluno.client.get(
        reverse("sugestao", args=[sugestao.id])
    ).content.decode()

    assert "Vale a pena." in corpo
    assert "equipe@meshcraft.test" not in corpo
    assert "meshcraft.test" not in corpo


def test_o_comentario_escrito_aparece_na_conversa(caixa):
    sugestao = caixa.publicar("Legendas nas aulas")
    caixa.aluno.client.post(
        reverse("comentar", args=[sugestao.id]), {"texto": "Assisto no ônibus."}
    )

    corpo = caixa.aluno.client.get(
        reverse("sugestao", args=[sugestao.id])
    ).content.decode()

    assert 'class="conversa"' in corpo
    assert "Assisto no ônibus." in corpo


# ---------------------------------------------------------------------------
# Nova ideia: a busca de duplicata NA FRENTE
# ---------------------------------------------------------------------------


def test_o_formulario_confere_antes_de_publicar_e_a_conferencia_nao_cria_nada(caixa):
    caixa.publicar("Legendas nas aulas gravadas")

    vazio = caixa.aluno.client.get(reverse("nova_sugestao")).content.decode()
    assert "Conferir se já existe" in vazio
    assert "Publicar assim mesmo" not in vazio, (
        "o botão de publicar apareceu antes da conferência — a busca de "
        "duplicata deixou de estar na frente"
    )

    conferencia = caixa.aluno.client.post(
        reverse("nova_sugestao"),
        {
            "titulo": "Legendas nos vídeos",
            "problema": "Não ouço.",
            "categoria": "curso",
        },
    )
    corpo = conferencia.content.decode()

    assert conferencia.status_code == 200
    assert "Isto já foi sugerido?" in corpo
    assert "Legendas nas aulas gravadas" in corpo
    assert "Publicar assim mesmo" in corpo
    assert Sugestao.objects.count() == 1, "a conferência publicou alguma coisa"


def test_a_categoria_escolhida_sobrevive_a_conferencia(caixa):
    """O estado mora no formulário, não em JavaScript: quem volta da
    conferência não reescolhe a categoria do zero."""
    corpo = caixa.aluno.client.post(
        reverse("nova_sugestao"),
        {"titulo": "Ideia nova", "problema": "Doi assim.", "categoria": "curso"},
    ).content.decode()

    assert re.search(r'value="curso"\s+checked', corpo), corpo[-1200:]


# ---------------------------------------------------------------------------
# O rosto sob o prefixo público — o regime da VPS
# ---------------------------------------------------------------------------


@pytest.fixture
def sob_prefixo(settings):
    """O env da VPS mais o que o SERVIDOR faz e o client de teste não faz.

    O prefixo é de THREAD e o Django não o limpa entre testes: sem o
    `clear_script_prefix()` na saída, ele vaza para quem rodar depois.
    """
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    yield
    clear_script_prefix()


def test_a_folha_de_estilo_sai_com_o_prefixo_publico(dentro, sugestao, sob_prefixo):
    """O guarda que separa `{% url %}` de `{% static %}`.

    `{% static %}` devolveria `/static/sugestoes/caixa.css` — endereço que, em
    `meshcraft.top`, o Traefik entrega ao `funil` (catch-all na raiz), não à
    Caixa. O rosto chegaria sem estilo em produção, e SÓ em produção.
    """
    corpo = dentro.client.get("/").content.decode()

    assert f'href="{PREFIXO}/static/sugestoes/caixa.css"' in corpo, (
        "a folha de estilo saiu sem o prefixo público — em meshcraft.top esse "
        "endereço é do funil, não da Caixa."
    )


def test_a_borda_publica_entrega_a_folha_de_estilo(sob_prefixo):
    """A outra metade: o endereço acima RESOLVE quando o Traefik o entrega.

    Pela borda pública a request line chega ao uvicorn COM o prefixo (o Traefik
    não o remove), e é aí que `armadilhas/083` mora: sem a rota `estatico` no
    urlconf, isto seria 404 com `DEBUG=0` e todos os settings certos.
    """
    resposta = async_to_sync(AsyncClient().get)(
        f"{PREFIXO}/static/sugestoes/caixa.css",
        headers={"x-forwarded-proto": "https"},
    )

    assert resposta.status_code == 200, resposta.status_code
    assert b"--laranja" in b"".join(resposta.streaming_content)


# ---------------------------------------------------------------------------
# O sino VESTIDO (EVO-31): a mesma lógica do EVO-21, com a cara do quadro
# ---------------------------------------------------------------------------


def test_a_pagina_de_avisos_fala_a_lingua_do_quadro(dentro, aviso):
    """A vestimenta, medida pelas peças que ela empresta do quadro.

    O aviso deixou de ser um parágrafo solto e virou cartão: selo de status (a
    mesma peça do card da grade), a mudança desenhada como `de → para`, e a nota
    da equipe dentro de uma `.ficha` — a peça que a página da sugestão já usa
    para o texto da equipe. Um teste que só olhasse o texto continuaria verde com
    a página crua de antes.
    """
    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert 'class="avisos"' in corpo, "a lista de avisos não virou a pilha de cartões"
    assert 'class="aviso nao-lido"' in corpo, "o não-lido não se anuncia na moldura"
    assert f'class="selo selo-{aviso.status_novo}"' in corpo
    assert 'class="ficha"' in corpo, "a nota da equipe ficou fora da ficha"
    assert 'rel="stylesheet"' in corpo


def test_o_aviso_leva_para_a_ideia_e_o_lido_some_da_lista_de_nao_lidos(dentro, aviso):
    """O cartão é caminho, não recado morto: dele se chega à ideia.

    E a segunda metade é o comportamento do EVO-21 continuando de pé por baixo
    da roupa nova — marcar como lido tira a marca da tela, não só do banco.
    """
    corpo = dentro.client.get(reverse("avisos")).content.decode()
    assert f'href="{reverse("sugestao", args=[aviso.sugestao.id])}"' in corpo
    assert ">novo<" in corpo

    dentro.client.post(reverse("marcar_aviso_lido", args=[aviso.id]))
    depois = dentro.client.get(reverse("avisos")).content.decode()

    assert 'class="aviso nao-lido"' not in depois
    assert ">novo<" not in depois
    assert "Marcar como lido" not in depois
    assert aviso.sugestao.titulo in depois, "o aviso lido sumiu da lista"


def test_o_sino_continua_contando_no_trilho_da_propria_pagina_de_avisos(dentro, aviso):
    """A contagem do EVO-21 não pode ter sido perdida na vestimenta.

    O guarda-mestre disso é `test_o_sino_de_toda_pagina_conta_so_os_meus`, que
    mede pelo quadro. Este mede na página nova, que é a que mudou — e afirma o
    nome acessível exatamente como ele é escrito na moldura (`avisos (N)`, em
    minúsculas), porque é assim que o outro guarda o lê.
    """
    corpo = " ".join(dentro.client.get(reverse("avisos")).content.decode().split())

    assert "avisos (1)" in corpo
    assert '<span class="contador" aria-hidden="true">1</span>' in corpo


def test_quem_nao_entrou_nao_alcanca_o_rosto(client, sugestao):
    """O rosto não afrouxou nada: continua valendo que a Caixa é de quem tem
    matrícula, inclusive para só olhar (`DECISAO-EVO-01` §2)."""
    for endereco in (
        reverse("quadro"),
        f"{reverse('quadro')}?ordem=novas",
        reverse("nova_sugestao"),
        reverse("sugestao", args=[sugestao.id]),
    ):
        resposta = client.get(endereco)
        assert resposta.status_code == 302, f"{endereco}: {resposta.status_code}"
        assert resposta["Location"] == reverse("entrar")
