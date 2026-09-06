"""A tela `/admin/mapa/` — o mapa do site (30/08/2026).

O que estes guardas protegem:

1. **A tela serve o arquivo do repositório** (`painel/mapa-do-site.json`), e não
   uma lista própria. Uma segunda lista aqui dentro seria a duplicação que o
   `CLAUDE.md` proíbe — e o dia em que as duas divergissem, o dono estaria
   olhando a planta errada da casa.
2. **Nenhum endereço some no caminho**: todo título do arquivo chega ao HTML.
   Uma linha que some não deixa rastro — é a pior forma de perder um fato.
3. **Molde não vira link.** `/forum/t/<int:topico_id>` não é um lugar; oferecê-lo
   como link manda o dono para um 404 e ele conclui que o site quebrou.
4. **Mapa ausente se DECLARA** (500 + explicação), nunca vira página vazia — a
   mesma lei do painel ausente. "Este site não tem endereço nenhum" seria a
   mentira mais convincente que esta tela poderia contar.
5. **A porta continua sendo a porta**: sem crachá, esta página não abre.
"""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import mapa_do_site, robos

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _arquivo() -> dict:
    caminho = mapa_do_site.arquivo_do_mapa()
    assert caminho is not None, (
        "o mapa do site não foi encontrado — em produção ele vem em "
        "`painel_embutido/`, num checkout em `painel/`. Se este assert falhou, "
        "a tela do dono abriria em 500."
    )
    return json.loads(caminho.read_text(encoding="utf-8"))


@respx.mock
def test_a_pagina_abre_em_areas_com_a_legenda_dos_publicos():
    """Desde 06/09/2026 o eixo é a ÁREA do site, e o público é um selo.

    As duas coisas são medidas aqui porque as duas são promessas da tela: as
    áreas principais aparecem como faixas, e a legenda continua explicando o
    que cada selo quer dizer. Antes, o público era o eixo e a mesma área do
    site ficava partida em quatro lugares distantes.
    """
    resposta = _dentro().get(reverse("mapa_do_site"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    for area in ("A vitrine e a porta de entrada", "A sala de aula", "O fórum"):
        assert area in html, f"a área {area!r} sumiu da tela"
    for titulo in ("Para quem só visita", "Para quem é aluno", "Para você"):
        assert titulo in html
    assert "Só para as máquinas" in html


@respx.mock
def test_nenhum_endereco_do_arquivo_some_da_tela():
    """Todo título declarado chega ao HTML — inclusive os gestos, dentro do
    `<details>`. Uma entrada que some não deixa rastro nenhum."""
    html = _dentro().get(reverse("mapa_do_site")).content.decode()
    sumidos = [e["titulo"] for e in _arquivo()["enderecos"] if e["titulo"] not in html]
    assert not sumidos, f"sumiram da tela: {sumidos}"


@respx.mock
def test_a_conta_da_tela_e_a_do_arquivo():
    """O número grande da capa é contado do arquivo, nunca digitado."""
    resposta = _dentro().get(reverse("mapa_do_site"))
    assert resposta.context["total"] == len(_arquivo()["enderecos"])
    # As três contas da capa são DISJUNTAS e somam o total. Se um dia deixarem
    # de somar, é porque uma entrada caiu em duas — e o dono estaria contando
    # a mesma página duas vezes na tela.
    assert (
        resposta.context["total_telas"]
        + resposta.context["total_gestos"]
        + resposta.context["total_maquina"]
        == resposta.context["total"]
    )
    assert not resposta.context["orfas"], (
        "endereço que nenhuma área da árvore acolhe: ele aparece numa faixa "
        "amarela em vez de sumir, mas o lugar de consertar é `AREAS`"
    )


@respx.mock
def test_molde_nao_vira_link_e_exemplo_vira():
    html = _dentro().get(reverse("mapa_do_site")).content.decode()
    assert 'href="/forum/t/' not in html, "molde oferecido como link dá 404"
    assert 'href="/forum/a/avisos"' in html, "o exemplo concreto é clicável"
    assert 'href="/forum/"' in html, "o endereço concreto é clicável"


@respx.mock
def test_gesto_nao_vira_link():
    """Clicar num gesto não pode ser possível: alguns MUDAM a vida de alguém."""
    html = _dentro().get(reverse("mapa_do_site")).content.decode()
    assert 'href="/admin/escola/alunos/decidir"' not in html
    assert "/admin/escola/alunos/decidir" in html, "mas ele está no mapa"


@respx.mock
def test_mapa_ausente_diz_isso_em_voz_alta(monkeypatch):
    monkeypatch.setattr(mapa_do_site, "diretorio_do_painel", lambda: None)
    resposta = _dentro().get(reverse("mapa_do_site"))
    assert resposta.status_code == 500
    assert "não veio nesta versão" in resposta.content.decode()


@respx.mock
def test_arquivo_torto_nao_vira_mapa_pela_metade(monkeypatch, tmp_path):
    torto = tmp_path / "mapa-do-site.json"
    torto.write_text('{"enderecos": ', encoding="utf-8")
    monkeypatch.setattr(mapa_do_site, "arquivo_do_mapa", lambda: torto)
    resposta = _dentro().get(reverse("mapa_do_site"))
    assert resposta.status_code == 500


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    """Quem não passou pela porta não vê a planta da casa."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    resposta = Client().get(reverse("mapa_do_site"))
    assert resposta.status_code != 200


# --------------------------------------------------------------------------
# A BUSCA (30/08/2026) — formulário do servidor, sem script
# --------------------------------------------------------------------------


@respx.mock
def test_a_busca_encolhe_a_lista_e_diz_de_quantos():
    resposta = _dentro().get(reverse("mapa_do_site"), {"q": "forum"})
    assert resposta.status_code == 200
    assert resposta.context["achados"] < resposta.context["total"]
    assert resposta.context["achados"] > 0
    assert "O fórum da escola" in resposta.content.decode()


@respx.mock
def test_a_busca_ignora_acento_e_maiuscula():
    """O dono digita 'sugestoes' no celular tanto quanto 'Sugestões'."""
    com = _dentro().get(reverse("mapa_do_site"), {"q": "Sugestões"}).context["achados"]
    sem = _dentro().get(reverse("mapa_do_site"), {"q": "sugestoes"}).context["achados"]
    assert com == sem > 0


@respx.mock
def test_a_busca_olha_tambem_o_endereco_e_a_nota():
    """Procurar por um pedaço de caminho encontra a linha."""
    resposta = _dentro().get(reverse("mapa_do_site"), {"q": "/healthz"})
    assert resposta.context["achados"] > 0


@respx.mock
def test_busca_sem_resultado_diz_isso_e_oferece_a_volta():
    resposta = _dentro().get(reverse("mapa_do_site"), {"q": "xyzzy-nao-existe"})
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Nenhum endereço com essa palavra" in html
    assert resposta.context["achados"] == 0


@respx.mock
def test_sem_busca_a_lista_e_inteira():
    resposta = _dentro().get(reverse("mapa_do_site"))
    assert resposta.context["achados"] == resposta.context["total"]
    assert resposta.context["procurado"] == ""


# --------------------------------------------------------------------------
# A LUZ de "está no ar?" — quem pergunta é o navegador do dono
# --------------------------------------------------------------------------


@respx.mock
def test_as_portas_principais_ganham_luz_e_o_resto_nao():
    resposta = _dentro().get(reverse("mapa_do_site"))
    sondados = [e["sonda"] for e in _arquivo()["enderecos"] if e.get("sonda")]
    assert len(sondados) >= 5, "o mapa deveria marcar as portas principais"
    html = resposta.content.decode()
    for entrada in _arquivo()["enderecos"]:
        alvo = entrada.get("exemplo") or entrada["endereco"]
        marcado = f'data-sonda="{alvo}"' in html
        assert marcado == bool(entrada.get("sonda")), f"{alvo}: sonda fora do lugar"


@respx.mock
def test_nenhum_gesto_e_sondado():
    """A cerca que impede um dano: sondar /entrar/sair deslogaria o dono."""
    html = _dentro().get(reverse("mapa_do_site")).content.decode()
    for entrada in _arquivo()["enderecos"]:
        if entrada.get("gesto"):
            alvo = entrada.get("exemplo") or entrada["endereco"]
            assert f'data-sonda="{alvo}"' not in html


@respx.mock
def test_a_ilha_de_script_entra_no_csp_por_hash_e_nunca_por_unsafe_inline():
    import base64
    import hashlib
    import re as _re

    resposta = _dentro().get(reverse("mapa_do_site"))
    csp = resposta["Content-Security-Policy"]
    ilhas = _re.findall(
        rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", resposta.content, _re.DOTALL
    )
    assert ilhas, "a página deveria ter a ilha da luz — sem ela o teste é vazio"
    for ilha in ilhas:
        h = base64.b64encode(hashlib.sha256(ilha).digest()).decode()
        assert f"'sha256-{h}'" in csp, "o navegador bloquearia a luz"
    assert "'unsafe-inline'" not in csp


@respx.mock
def test_o_csp_proprio_desta_pagina_nao_esquece_o_estilo():
    """Esta resposta traz política pronta, então a da porta não se aplica —
    e sem o hash do estilo a página voltaria a chegar sem desenho nenhum
    (`armadilhas/199`)."""
    import base64
    import hashlib
    import re as _re

    resposta = _dentro().get(reverse("mapa_do_site"))
    csp = resposta["Content-Security-Policy"]
    for folha in _re.findall(
        rb"<style[^>]*>(.*?)</style>", resposta.content, _re.DOTALL
    ):
        h = base64.b64encode(hashlib.sha256(folha).digest()).decode()
        assert f"'sha256-{h}'" in csp, "o navegador bloquearia o estilo desta página"


@respx.mock
def test_a_luz_so_pergunta_a_este_mesmo_site():
    csp = _dentro().get(reverse("mapa_do_site"))["Content-Security-Policy"]
    assert "connect-src 'self'" in csp


# --------------------------------------------------------------- a árvore
#
# Os guardas da hierarquia, pedida pelo mantenedor em 06/09/2026. Eles medem as
# três promessas que a tela passou a fazer: toda página cabe numa área, filha
# fica embaixo da mãe, e botão não vira galho.


def _linha(resposta, endereco: str) -> dict:
    """A linha da árvore de um endereço, olhada de dentro (contexto, não HTML).

    Medir pelo contexto e não pelo texto é o que faz este teste falhar por
    hierarquia errada em vez de falhar por uma vírgula no desenho.
    """
    for area in resposta.context["areas"]:
        for item in area["linhas"]:
            if item["endereco"] == endereco:
                return item
    raise AssertionError(f"{endereco} não está em nenhuma área da árvore")


@respx.mock
def test_toda_pagina_do_arquivo_cabe_em_alguma_area():
    """O guarda que impede a lista de áreas de envelhecer em silêncio.

    Rota nova exige entrada em `painel/mapa-do-site.json`, que é da célula
    `admin` — então esta suíte roda no PR que a criar. Se o endereço novo não
    couber em nenhuma área, é aqui que ele reprova, com o conserto escrito.
    """
    resposta = _dentro().get(reverse("mapa_do_site"))
    orfas = [e["endereco"] for e in resposta.context["orfas"]]
    assert not orfas, (
        f"estes endereços não couberam em nenhuma área do mapa: {orfas}.\n"
        "Conserto: em `services/admin/apps/core/mapa_do_site.py`, acrescente o "
        "prefixo deles a uma das áreas de `AREAS`, ou crie uma área nova com "
        "nome de gente. Sem isso eles aparecem numa faixa amarela solta, fora "
        "da árvore."
    )
    # E o caminho de volta: área declarada que não acolhe nada é lista morta.
    nas_areas = sum(
        1 + len(linha["gestos"])
        for area in resposta.context["areas"]
        for linha in area["linhas"]
    )
    assert nas_areas == resposta.context["total"], (
        f"a árvore mostra {nas_areas} endereços e o arquivo tem "
        f"{resposta.context['total']} — algum sumiu no caminho"
    )


@respx.mock
def test_a_sub_pagina_fica_embaixo_da_pagina():
    """A promessa da árvore: quem está dentro aparece dentro.

    Os três degraus medidos são reais e de partes diferentes do site, para o
    teste não passar por acaso com um caso só.
    """
    resposta = _dentro().get(reverse("mapa_do_site"))
    escadas = (
        (
            "/admin/",
            "/admin/escola/",
            "/admin/escola/alunos/",
            "/admin/escola/alunos/recusados",
        ),
        ("/forum/", "/forum/a/<slug:slug>"),
        ("/cursos/", "/cursos/<slug:curso>/"),
    )
    for escada in escadas:
        niveis = [_linha(resposta, endereco)["nivel"] for endereco in escada]
        assert niveis == sorted(niveis) and len(set(niveis)) == len(niveis), (
            f"a escada {escada} saiu nos níveis {niveis} — sub-página que não "
            "fica embaixo da página é uma árvore que não é árvore"
        )


@respx.mock
def test_o_botao_mora_dentro_da_pagina_dele():
    """96 dos 222 endereços são botões. Como galhos, dobrariam a altura."""
    resposta = _dentro().get(reverse("mapa_do_site"))
    recusados = _linha(resposta, "/admin/escola/alunos/recusados")
    apagar = [g["endereco"] for g in recusados["gestos"]]
    assert "/admin/escola/alunos/recusados/apagar" in apagar
    for area in resposta.context["areas"]:
        for item in area["linhas"]:
            assert item["endereco"] != "/admin/escola/alunos/recusados/apagar", (
                "o botão virou galho próprio da árvore em vez de etiqueta da "
                "página a que pertence"
            )


@respx.mock
def test_a_busca_traz_a_pagina_de_cima_junto():
    """Peneira que joga fora as mães devolve galho solto no ar.

    `recusados/apagar` sem `A lista dos recusados` em cima não diz o que apaga.
    """
    resposta = _dentro().get(reverse("mapa_do_site"), {"q": "recusado"})
    assert resposta.status_code == 200
    enderecos = [
        item["endereco"]
        for area in resposta.context["areas"]
        for item in area["linhas"]
    ]
    assert "/admin/escola/alunos/recusados" in enderecos
    assert "/admin/escola/alunos/" in enderecos, "a mãe sumiu e o galho ficou solto"
    assert "/admin/" in enderecos, "a raiz da área sumiu"
    assert "/forum/" not in enderecos, "a busca não peneirou nada"


@respx.mock
def test_a_area_de_cada_endereco_e_uma_so():
    """Prefixo mais longo vence, e nenhum endereço cai em duas áreas.

    Sem essa regra `/admin` e um futuro `/admin/escola` disputariam a mesma
    linha, e o dono contaria a mesma página duas vezes.
    """
    assert mapa_do_site.area_de("/admin/escola/alunos/") == "administracao"
    assert mapa_do_site.area_de("/") == "vitrine"
    assert mapa_do_site.area_de("/forum/") == "forum"
    assert mapa_do_site.area_de("-") == mapa_do_site.AREA_INTERNA
    # A raiz cobre só ela mesma: sem isso `/` engoliria o site inteiro.
    assert mapa_do_site.area_de("/cursos/") == "sala"
    # Endereço que ninguém previu devolve None, e a tela o mostra em voz alta.
    assert mapa_do_site.area_de("/coisa-que-ninguem-declarou") is None


# ------------------------------------------------------ o que está em obra


def _fila_de_mentira(tmp_path, monkeypatch):
    """Uma fila embutida como o deploy a deixaria, com os dois lados medidos.

    A mistura é de propósito: duas tarefas abertas em lugares diferentes, e uma
    já concluída que NÃO pode aparecer como obra. Sem a concluída no dado, o
    guarda passaria mesmo com a regra de "em aberto" adulterada — foi o que
    aconteceu na primeira mutação (`armadilhas/195`).
    """
    pasta = tmp_path / "fila_embutida"
    pasta.mkdir(parents=True)
    (pasta / "estados.json").write_text(
        json.dumps(
            {
                "TAR-001": {
                    "estado": "concluída",
                    "titulo": "Coisa que já ficou pronta",
                    "toca": ["forum"],
                },
                "TAR-002": {
                    "estado": "na fila",
                    "titulo": "Coisa que ainda vai ser feita",
                    "toca": ["forum"],
                },
                "TAR-003": {
                    "estado": "bloqueada",
                    "titulo": "Coisa que parou no meio",
                    "toca": ["quiz", "funil"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))


@respx.mock
def test_o_que_esta_em_obra_vem_da_fila_e_nao_de_uma_lista_daqui(tmp_path, monkeypatch):
    """A segunda metade do pedido: o que existe, e o que ainda está sendo feito.

    Os estados são escritos AQUI por extenso, e não lidos de `EM_ABERTO`: um
    teste que lê a mesma constante que deveria vigiar passa mesmo quando ela é
    adulterada.
    """
    _fila_de_mentira(tmp_path, monkeypatch)
    resposta = _dentro().get(reverse("mapa_do_site"))
    html = resposta.content.decode()
    assert "Ainda sendo construído" in html

    obra = resposta.context["obra"]
    assert obra is not None, "a fila estava lá e a tela não a leu"
    assert obra["total"] == 2, "a tarefa já concluída entrou na conta do que falta"
    assert "Coisa que já ficou pronta" not in html
    assert "Coisa que ainda vai ser feita" in html
    assert "Coisa que parou no meio" in html

    for lugar in obra["lugares"]:
        for tarefa in lugar["tarefas"]:
            assert tarefa["estado"] not in ("concluída", "cancelada")

    # O `toca` vira lugar que o dono reconhece, e uma tarefa que mexe em dois
    # aparece nos dois: por isso a soma dos lugares passa do total, e a tela diz
    # isso com todas as letras em vez de deixar a conta parecer errada.
    lugares = {lugar["nome"] for lugar in obra["lugares"]}
    assert "o fórum" in lugares and "o quiz" in lugares
    assert sum(lugar["quantas"] for lugar in obra["lugares"]) == 3


@respx.mock
def test_fila_ausente_nao_vira_nada_em_obra(monkeypatch):
    """Sem a fila, a tela DIZ que não a leu. "Nada em obra" seria mentira."""
    monkeypatch.setattr(mapa_do_site, "diretorio_da_fila", lambda: None)
    html = _dentro().get(reverse("mapa_do_site")).content.decode()
    assert "A fila de trabalho não veio nesta versão do site." in html
    assert "Ainda sendo construído" in html
