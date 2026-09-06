"""As duas telas da sala e os dois gestos, do lado da pessoa que as abre.

O que este arquivo protege, e por que cada coisa:

1. **O mapa** mostra as 34 portas em três Partes e doze Blocos, o estado de
   cada uma, e a próxima aberta em destaque.
2. **A aula** mostra as 16 peças na ORDEM_CANONICA, renderizadas de Markdown,
   e as duas internas NUNCA aparecem no HTML, nem quando têm texto.
3. **Aula em rascunho é 404**; **porta trancada volta ao mapa** sem conteúdo;
   **abrir** leva `disponivel` a `em_producao`.
4. **O vídeo** só é embutido quando é YouTube ou Vimeo; qualquer outro é link.
5. **As pausas** têm um formulário cada; registrar cria `RegistroDePausa`,
   repetir é inerte, e campo vazio é recusado com frase.
6. **O quiz** esconde a resposta-modelo até a autoavaliação ser gravada.
7. **O checkpoint** tem o formulário de entrega por link, na aula, apontando
   para o gesto do checkpoint (a jornada inteira mora em `test_envio.py`).
8. **O CSS responde sob o prefixo** e **todo link interno sai com o prefixo**
   (`armadilhas/083`, `/102`, `/081`).
9. **O menu do topo** vem do catálogo e falha para "sem menu", nunca tela
   quebrada; **o rodapé** está nas duas telas.
"""

from __future__ import annotations

import re

import httpx
import pytest
from django.urls import clear_script_prefix, reverse, set_script_prefix

from apps.core import menu as motor_do_menu
from apps.cursos import progresso as portas
from apps.cursos.models import Aula, Peca, Progresso, RegistroDePausa
from tests.conftest import (
    ANA,
    CATALOGO,
    COOKIE,
    URL_DO_MENU,
    dublar_matricula,
    dublar_sessao,
    publicar,
)

pytestmark = pytest.mark.django_db

# O prefixo público desta célula. Em produção quem o aplica é
# `FORCE_SCRIPT_NAME`; aqui ele entra pelo test client, que é o único jeito de
# medir honestamente o que `{% url %}` gera sob prefixo (`armadilhas/081`).
PREFIXO = {"SCRIPT_NAME": "/cursos"}


def abrir(client, endereco, **extra):
    return client.get(endereco, HTTP_COOKIE=COOKIE, **extra)


def corpo_de(resposta) -> str:
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


# ---------------------------------------------------------------- 1. o mapa
def test_o_mapa_tem_as_34_portas_em_tres_partes_e_doze_blocos(aluna, client):
    corpo = corpo_de(abrir(client, reverse("mapa")))
    assert corpo.count("<h2>Parte ") == 3
    assert corpo.count('<div class="bloco">') == 12
    assert corpo.count('<li class="porta ') == 34
    assert "Encomenda 00" in corpo and "Encomenda Bônus" in corpo


def test_a_proxima_porta_aberta_fica_em_destaque(aluna, aula_publicada, client):
    corpo = corpo_de(abrir(client, reverse("mapa")))
    assert "Sua porta aberta agora:" in corpo
    assert 'class="porta-atual"' in corpo
    assert corpo.count(" atual") == 1


def test_a_porta_aberta_em_rascunho_e_dita_como_em_preparo(aluna, client):
    """A E00 nasce disponível antes de a escola publicá-la: o mapa não promete
    um link que responderia 404."""
    corpo = corpo_de(abrir(client, reverse("mapa")))
    assert "Em preparo" in corpo
    assert 'href="/E00"' not in corpo


def test_o_mapa_mostra_o_estado_de_cada_porta(aluna, aula_publicada, client):
    corpo = corpo_de(abrir(client, reverse("mapa")))
    assert ">Disponível<" in corpo
    assert corpo.count(">Trancada<") == 33


# ---------------------------------------------------------------- 2. a aula
def test_a_aula_mostra_as_16_pecas_na_ordem_canonica(aluna, aula_publicada, client):
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    posicoes = [corpo.index(f'id="peca-{tipo}"') for tipo in Peca.ORDEM_CANONICA]
    assert posicoes == sorted(posicoes)
    assert corpo.count('class="peca"') == 16
    # Renderizadas de Markdown: o `**` virou <strong>, e o `#` virou título.
    assert "<strong>pedido</strong>" in corpo
    assert "<h1>pedido</h1>" in corpo


def test_as_duas_pecas_internas_nunca_aparecem(aluna, aula_publicada, client):
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert "SEGREDO-DO-ROTEIRO" not in corpo
    assert "SEGREDO-DO-MENTOR" not in corpo
    assert 'id="peca-roteiro"' not in corpo
    assert 'id="peca-guia_do_mentor"' not in corpo


def test_peca_sem_texto_nao_vira_secao_vazia(aluna, aula_publicada, client):
    Peca.objects.filter(aula=aula_publicada, tipo=Peca.Tipo.DRILLS).update(texto="")
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert 'id="peca-drills"' not in corpo
    assert corpo.count('class="peca"') == 15


def test_html_dentro_de_uma_peca_chega_escapado_na_pagina(
    aluna, aula_publicada, client
):
    Peca.objects.filter(aula=aula_publicada, tipo=Peca.Tipo.PEDIDO).update(
        texto="<script>alert(1)</script>"
    )
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


# ------------------------------------------------------ 3. rascunho e porta
def test_aula_em_rascunho_e_404_para_o_aluno(aluna, esqueleto, client):
    aula = esqueleto.aulas.get(numero="E00")
    assert aula.estado == Aula.Estado.RASCUNHO
    assert abrir(client, reverse("aula", args=["E00"])).status_code == 404


def test_aula_que_nao_existe_e_404(aluna, esqueleto, client):
    assert abrir(client, reverse("aula", args=["E99"])).status_code == 404


def test_porta_trancada_volta_ao_mapa_sem_mostrar_o_conteudo(aluna, esqueleto, client):
    publicar(esqueleto.aulas.get(numero="E01"))
    resposta = abrir(client, reverse("aula", args=["E01"]))
    assert resposta.status_code == 302
    mapa_do_curso = reverse("curso", args=["profissional"])
    assert resposta["Location"] == f"{mapa_do_curso}?recado=trancada"
    corpo = corpo_de(abrir(client, resposta["Location"]))
    assert "Essa porta ainda está trancada" in corpo
    assert "Texto da peça" not in corpo


def test_abrir_a_aula_leva_disponivel_a_em_producao(aluna, aula_publicada, client):
    abrir(client, reverse("mapa"))
    assert Progresso.objects.get().estado == Progresso.Estado.DISPONIVEL
    abrir(client, reverse("aula", args=["E00"]))
    assert Progresso.objects.get().estado == Progresso.Estado.EM_PRODUCAO


def test_a_aula_abre_direto_sem_passar_pelo_mapa(aluna, aula_publicada, client):
    """A E00 nasce na primeira visita a QUALQUER tela da sala."""
    resposta = abrir(client, reverse("aula", args=["E00"]))
    assert resposta.status_code == 200
    assert Progresso.objects.get().estado == Progresso.Estado.EM_PRODUCAO


# ---------------------------------------------------------------- 4. o vídeo
@pytest.mark.parametrize(
    "url, embutido",
    [
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
        (
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
        (
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
        ("https://vimeo.com/123456789", "https://player.vimeo.com/video/123456789"),
        (
            "https://player.vimeo.com/video/123456789",
            "https://player.vimeo.com/video/123456789",
        ),
    ],
)
def test_youtube_e_vimeo_entram_embutidos(aluna, esqueleto, client, url, embutido):
    publicar(esqueleto.aulas.get(numero="E00"), video_url=url)
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert f'<iframe src="{embutido}"' in corpo
    assert "Abrir o vídeo em outra aba" in corpo


@pytest.mark.parametrize(
    "url",
    [
        "https://drive.google.com/file/d/abc/view",
        "https://videos.exemplo/e00",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=<script>",
        "https://vimeo.com/nao-e-numero",
    ],
)
def test_qualquer_outro_video_e_link_simples_e_nunca_iframe(
    aluna, esqueleto, client, url
):
    publicar(esqueleto.aulas.get(numero="E00"), video_url=url)
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert "<iframe" not in corpo
    assert "Assistir ao vídeo" in corpo


def test_aula_sem_video_diz_isso(aluna, esqueleto, client):
    publicar(esqueleto.aulas.get(numero="E00"), video_url="")
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert "<iframe" not in corpo
    assert "Esta aula ainda não tem vídeo." in corpo


# --------------------------------------------------------------- 5. as pausas
def test_cada_pausa_tem_o_segundo_e_um_formulario_proprio(
    aluna, aula_publicada, client
):
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert "Pausa 1 aos 1:30" in corpo
    assert "Pausa 2 aos 4:00" in corpo
    assert corpo.count('action="' + reverse("registrar-pausa", args=["E00", 1])) == 1
    assert corpo.count('action="' + reverse("registrar-pausa", args=["E00", 2])) == 1
    assert 'name="campo_0"' in corpo and 'name="campo_1"' in corpo


def test_registrar_uma_pausa_cria_o_registro_e_volta_para_ela(
    aluna, aula_publicada, client
):
    resposta = client.post(
        reverse("registrar-pausa", args=["E00", 2]),
        {"campo_0": "tentei extrudar", "campo_1": "a face virou"},
        HTTP_COOKIE=COOKIE,
    )
    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?recado=pausa-registrada#pausa-2")

    registro = RegistroDePausa.objects.get()
    assert registro.pessoa.id_da_plataforma == ANA["id"]
    assert registro.pausa.ordem == 2
    assert registro.respostas == {
        "o que tentei": "tentei extrudar",
        "o que aconteceu": "a face virou",
    }
    corpo = corpo_de(abrir(client, resposta["Location"].split("#")[0]))
    assert "Registro guardado" in corpo
    assert "tentei extrudar" in corpo
    assert corpo.count('action="' + reverse("registrar-pausa", args=["E00", 2])) == 0


def test_registrar_a_mesma_pausa_de_novo_e_inerte(aluna, aula_publicada, client):
    for _ in range(2):
        client.post(
            reverse("registrar-pausa", args=["E00", 1]),
            {"campo_0": "um cubo"},
            HTTP_COOKIE=COOKIE,
        )
    assert RegistroDePausa.objects.count() == 1
    assert RegistroDePausa.objects.get().respostas == {
        "o que apareceu na tela": "um cubo"
    }


def test_campo_vazio_e_recusado_com_frase(aluna, aula_publicada, client):
    resposta = client.post(
        reverse("registrar-pausa", args=["E00", 2]),
        {"campo_0": "tentei", "campo_1": "   "},
        HTTP_COOKIE=COOKIE,
    )
    assert resposta.status_code == 302
    assert RegistroDePausa.objects.count() == 0
    corpo = corpo_de(abrir(client, resposta["Location"]))
    assert "Preencha todos os campos da pausa" in corpo


def test_pausa_que_nao_existe_e_404(aluna, aula_publicada, client):
    resposta = client.post(
        reverse("registrar-pausa", args=["E00", 9]), {}, HTTP_COOKIE=COOKIE
    )
    assert resposta.status_code == 404


def test_registrar_pausa_e_gesto_de_post(aluna, aula_publicada, client):
    assert abrir(client, reverse("registrar-pausa", args=["E00", 1])).status_code == 405


# ----------------------------------------------------------------- 6. o quiz
def test_a_resposta_modelo_fica_escondida_ate_gravar(aluna, aula_publicada, client):
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert "O que é um stud?" in corpo
    assert "MODELO-1" not in corpo and "MODELO-2" not in corpo
    assert 'name="resposta_0"' in corpo and 'name="resposta_1"' in corpo


def test_gravar_a_autoavaliacao_abre_a_resposta_modelo(aluna, aula_publicada, client):
    resposta = client.post(
        reverse("gravar-autoavaliacao", args=["E00"]),
        {"resposta_0": "a medida do Roblox", "resposta_1": "suavizar"},
        HTTP_COOKIE=COOKIE,
    )
    assert resposta.status_code == 302
    assert Progresso.objects.get().autoavaliacao["respostas"] == [
        "a medida do Roblox",
        "suavizar",
    ]
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert "MODELO-1" in corpo and "MODELO-2" in corpo
    assert "a medida do Roblox" in corpo
    assert 'name="resposta_0"' not in corpo


def test_resposta_vazia_no_quiz_e_recusada(aluna, aula_publicada, client):
    resposta = client.post(
        reverse("gravar-autoavaliacao", args=["E00"]),
        {"resposta_0": "x", "resposta_1": ""},
        HTTP_COOKIE=COOKIE,
    )
    assert Progresso.objects.get().autoavaliacao == {}
    corpo = corpo_de(abrir(client, resposta["Location"]))
    assert "Responda todas as perguntas" in corpo


def test_a_autoavaliacao_grava_uma_vez_so(aluna, aula_publicada, client):
    dados = {"resposta_0": "primeira", "resposta_1": "vez"}
    client.post(
        reverse("gravar-autoavaliacao", args=["E00"]), dados, HTTP_COOKIE=COOKIE
    )
    resposta = client.post(
        reverse("gravar-autoavaliacao", args=["E00"]),
        {"resposta_0": "segunda", "resposta_1": "vez"},
        HTTP_COOKIE=COOKIE,
    )
    assert Progresso.objects.get().autoavaliacao["respostas"] == ["primeira", "vez"]
    assert "já foi gravada" in corpo_de(abrir(client, resposta["Location"]))


def test_aula_sem_quiz_nao_mostra_a_secao(aluna, esqueleto, client):
    publicar(esqueleto.aulas.get(numero="E00"), quiz=[])
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    assert 'id="quiz"' not in corpo


# ----------------------------------------------------------- 7. o checkpoint
def test_o_checkpoint_tem_o_formulario_de_entrega_por_link(aluna, ana_pronta, client):
    """A jornada inteira (recusas, a entrega, "recebido em") está em
    `test_envio.py`; aqui só o lugar: o formulário mora na aula, aponta para o
    gesto do checkpoint, e o "aceito quando" continua acima dele."""
    corpo = corpo_de(abrir(client, reverse("aula", args=["E00"])))
    inicio = corpo.index('id="checkpoint"')
    checkpoint = corpo[inicio : corpo.index("</section>", inicio)]
    assert f'action="{reverse("entregar-checkpoint", args=["E00"])}"' in checkpoint
    assert 'name="arquivo"' in checkpoint
    assert ">Entregar<" in checkpoint
    assert "as arestas estão suaves" in checkpoint
    assert "O envio nasce no próximo degrau" not in checkpoint


# ------------------------------------------------ 8. o CSS e os links
@pytest.fixture
def sob_prefixo(settings):
    """O env da VPS mais o que o servidor faz e o client de teste não faz:
    `reverse()` lê um prefixo de thread que só o `ASGIHandler` preenche
    (`armadilhas/081`). Com ele ligado, os caminhos pedidos ao client são o
    `path_info` nu (`/`, `/E00`), como o Django os vê depois do corte."""
    settings.FORCE_SCRIPT_NAME = "/cursos"
    set_script_prefix("/cursos")
    yield
    clear_script_prefix()


def test_o_css_responde_sob_o_prefixo_com_os_bytes_do_arquivo(
    aluna, client, settings, sob_prefixo
):
    """`armadilhas/083` e `/102`: o `<link>` sai com o prefixo público, e uma
    requisição real pelo urlconf real, com DEBUG=0, devolve o arquivo."""
    assert settings.DEBUG is False
    corpo = corpo_de(abrir(client, "/"))
    links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', corpo)
    assert links == ["/cursos/static/cursos/sala.css"]
    resposta = client.get("/static/cursos/sala.css")
    assert resposta.status_code == 200
    assert "porta-atual" in corpo_de(resposta)


def test_travessia_de_diretorio_no_estatico_nao_passa(client):
    assert client.get("/static/../config/settings.py").status_code in (400, 404)
    assert client.get("/static/cursos/../../config/settings.py").status_code in (
        400,
        404,
    )


def test_todo_endereco_interno_sai_com_o_prefixo_publico(
    aluna, aula_publicada, client, sob_prefixo
):
    """`armadilhas/081`: sob SCRIPT_NAME, todo `href` e `action` da célula
    começa pelo prefixo. Endereço de fora (a capa, a entrada, os documentos)
    não é desta célula e fica de fora da régua."""
    for endereco in ("/", "/E00"):
        corpo = corpo_de(abrir(client, endereco))
        internos = [
            alvo
            for alvo in re.findall(r'(?:href|action)="([^"]+)"', corpo)
            if alvo.startswith("/") and alvo not in ("/", "/docs/", "/entrar/google")
        ]
        assert internos, endereco
        fora = [alvo for alvo in internos if not alvo.startswith("/cursos/")]
        assert fora == [], f"links sem o prefixo público em {endereco}: {fora}"


# ------------------------------------------------- 9. o menu e o rodapé
MENU = {
    "default_version": "completo",
    "versions": [
        {
            "slug": "completo",
            "name": "Menu completo",
            "items": [
                {"url": "/", "labels": {"pt-br": "Início", "en": "Home"}},
                {
                    "url": "/forum/",
                    "labels": {"pt-br": "Fórum"},
                    "audience": "logged_in",
                },
                {"url": "/cursos/", "labels": {"pt-br": "Curso"}},
                {"url": "/admin/", "labels": {"pt-br": "Painel"}, "audience": "staff"},
            ],
        }
    ],
    "pages": [],
}
SITE_DO_CATALOGO = {
    "id": "escola-a",
    "host": "testserver",
    "default_language": "pt-br",
    "menu": MENU,
}


@pytest.fixture
def par_do_menu(monkeypatch):
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-cursos-para-catalogo")
    motor_do_menu.limpar_cache()


def _menu(corpo: str) -> str:
    inicio = corpo.index('<nav class="menu-topo">')
    return corpo[inicio : corpo.index("</nav>", inicio)]


def test_o_menu_aparece_nas_duas_telas_e_esconde_a_area_atual(
    aluna, aula_publicada, rede, par_do_menu, client
):
    rede.get(URL_DO_MENU).mock(return_value=httpx.Response(200, json=SITE_DO_CATALOGO))
    for endereco in (reverse("mapa"), reverse("aula", args=["E00"])):
        barra = _menu(corpo_de(abrir(client, endereco, **PREFIXO)))
        assert "Início" in barra and "Home" not in barra
        assert 'href="/forum/"' in barra, "quem entrou vê o item logged_in"
        assert 'href="/cursos/"' not in barra, "o item da área atual some"
        assert 'href="/admin/"' not in barra, "papel aluno não é staff"


def test_o_menu_e_fail_open_catalogo_fora_do_ar_nao_derruba_a_sala(
    aluna, rede, par_do_menu, client
):
    rede.get(URL_DO_MENU).mock(side_effect=httpx.ConnectError("sem rede"))
    resposta = abrir(client, reverse("mapa"))
    assert resposta.status_code == 200
    assert "menu-topo" not in corpo_de(resposta)


def test_sem_par_com_o_catalogo_nenhuma_tentativa_de_rede(aluna, rede, client):
    """O estado real da célula até o passo do mantenedor: silencioso."""
    resposta = abrir(client, reverse("mapa"))
    assert resposta.status_code == 200
    assert "menu-topo" not in corpo_de(resposta)
    assert not any(str(c.request.url).startswith(CATALOGO) for c in rede.calls)


def test_o_menu_nao_custa_um_segundo_salto_a_identidade(
    aluna, rede, par_do_menu, client
):
    """A view pergunta quem é; o processador do menu reaproveita a resposta."""
    rede.get(URL_DO_MENU).mock(return_value=httpx.Response(200, json=SITE_DO_CATALOGO))
    abrir(client, reverse("mapa"), **PREFIXO)
    idas = [c for c in rede.calls if str(c.request.url).endswith("/sessao/completa")]
    assert len(idas) == 1


def test_o_visitante_ve_o_menu_de_quem_nao_entrou(
    env_dos_pares, esqueleto, rede, par_do_menu, client
):
    rede.get(URL_DO_MENU).mock(return_value=httpx.Response(200, json=SITE_DO_CATALOGO))
    barra = _menu(corpo_de(client.get(reverse("mapa"), **PREFIXO)))
    assert 'href="/forum/"' not in barra


def test_o_rodape_esta_nas_duas_telas_e_no_convite(
    env_dos_pares, rede, esqueleto, client
):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    publicar(esqueleto.aulas.get(numero="E00"))
    for endereco in (reverse("mapa"), reverse("aula", args=["E00"])):
        corpo = corpo_de(abrir(client, endereco))
        assert '<footer class="rodape rodape-completo">' in corpo, endereco
        assert "Todos os direitos reservados" in corpo
    convite = corpo_de(client.get(reverse("mapa")))
    assert '<footer class="rodape' in convite


def test_o_css_nao_leva_rodape(aluna, client):
    corpo = corpo_de(client.get(reverse("estatico", args=["cursos/sala.css"])))
    assert "<footer" not in corpo
