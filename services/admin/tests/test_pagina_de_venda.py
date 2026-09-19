"""A tela `/admin/paginas/` — onde o mantenedor escreve o texto da página de venda.

O que estes guardas protegem:

1. **A tela e o despacho dizem as MESMAS palavras.** As onze seções, os espaços
   de cada uma e a frase que explica cada espaço são transcritos de
   `docs/despachos/DESPACHO-COPY-DA-PAGINA-DE-OFERTA.md`. O guarda compara os
   dois caractere por caractere: a transcrição que envelhecer fica vermelha
   aqui, e não na cara dele.
2. **Espaço vazio não é erro.** Página nunca editada responde 404 no catálogo, e
   404 é folha em branco. Uma tela que tratasse isso como falha faria o primeiro
   uso parecer defeito.
3. **O que ele digitou não se perde.** Gravação recusada ou catálogo mudo
   devolvem a tela com o TEXTO DIGITADO, nunca com o que estava gravado. É o
   contrário da tela do menu, e de propósito: lá o conteúdo é a configuração,
   aqui o conteúdo é o trabalho dele.
4. **A sentinela da ferramenta 74 avisa e não bloqueia.** Ela aponta os cinco
   padrões que o mantenedor proibiu em 05/09/2026 e deixa ele publicar assim
   mesmo. Um bloqueio poria a máquina decidindo o que ele pode dizer.
5. **Rascunho e publicado são coisas diferentes na tela.** Salvar não muda o
   site; publicar muda e cria versão nova.
6. **Toda escrita deixa linha de auditoria**, inclusive a que falhou
   (`DECISAO-celula-admin.md` §3).
7. **A porta continua sendo a porta**: sem crachá, nada disto responde.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils.html import escape

from apps.auditoria.models import Registro
from apps.core import paginas

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"
RASCUNHO = f"{CATALOGO}/sites/{SITE_ID}/paginas/oferta/rascunho"
PUBLICAR = f"{CATALOGO}/sites/{SITE_ID}/paginas/oferta/publicar"

SITE = {"id": SITE_ID, "host": "testserver", "name": "Meshcraft", "active": True}

RAIZ_DO_REPO = Path(__file__).resolve().parents[3]
DESPACHO = RAIZ_DO_REPO / "docs" / "despachos" / "DESPACHO-COPY-DA-PAGINA-DE-OFERTA.md"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
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


def _site():
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json=SITE)
    )


def _corpo_do_rascunho(secoes, base_version=0) -> dict:
    return {
        "site_id": SITE_ID,
        "slug": "oferta",
        "base_version": base_version,
        "secoes": secoes,
        "atualizado_em": "2026-09-19T12:00:00Z",
    }


def _folha_em_branco():
    """O catálogo responde 404: esta página nunca foi editada."""
    _site()
    respx.get(RASCUNHO).mock(
        return_value=httpx.Response(
            404, json={"detail": "esta página ainda não tem rascunho"}
        )
    )


def _com_rascunho(secoes, base_version=0):
    _site()
    respx.get(RASCUNHO).mock(
        return_value=httpx.Response(200, json=_corpo_do_rascunho(secoes, base_version))
    )


def _texto(resposta) -> str:
    return resposta.content.decode()


# ---------------------------------------------------------------------------
# 1. A tela e o despacho dizem as mesmas palavras
# ---------------------------------------------------------------------------
def _despacho_declarado() -> tuple[list, dict]:
    """As onze seções e a frase de cada espaço, lidas do documento dele.

    Derivar em vez de copiar é o que faz esta comparação valer alguma coisa:
    duas listas escritas à mão concordariam por terem sido copiadas uma da
    outra, e divergiriam na primeira correção feita só de um lado.
    """
    assert DESPACHO.is_file(), (
        f"{DESPACHO} não existe. Este guarda não tem o que medir, e isso não é "
        "um OK — [INV-CI01]."
    )
    texto = DESPACHO.read_text(encoding="utf-8")

    ordem = []
    for linha in texto.splitlines():
        if not linha.startswith("| "):
            continue
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(celulas) != 4 or not celulas[0].isdigit():
            continue
        nome = celulas[1].strip("`")
        espacos = []
        for pedaco in celulas[3].split(","):
            pedaco = pedaco.strip()
            faixa = re.fullmatch(r"`(\w+?)_(\d+)` a `(\w+?)_(\d+)`", pedaco)
            if faixa:
                base, primeiro, _, ultimo = faixa.groups()
                espacos += [
                    f"{base}_{n}" for n in range(int(primeiro), int(ultimo) + 1)
                ]
            else:
                espacos.append(pedaco.strip("`"))
        ordem.append((nome, celulas[2], tuple(espacos)))

    frases = {}
    secao = None
    for linha in texto.splitlines():
        cabecalho = re.match(r"## Seção \d+: `(\w+)`", linha)
        if cabecalho:
            secao = cabecalho.group(1)
            continue
        if secao is None or not linha.startswith("| `"):
            continue
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(celulas) != 4:
            continue
        rotulo = celulas[0].strip("`")
        faixa = re.fullmatch(r"(\w+?)_(\d+)` a `(\w+?)_(\d+)", rotulo)
        alvos = (
            [
                f"{faixa.group(1)}_{n}"
                for n in range(int(faixa.group(2)), int(faixa.group(4)) + 1)
            ]
            if faixa
            else [rotulo]
        )
        for alvo in alvos:
            frases[f"{secao}.{alvo}"] = celulas[1]

    assert len(ordem) == 11, (
        f"o despacho declarou {len(ordem)} seções em vez de onze — falha de "
        "medição, não notícia ([INV-CI01])."
    )
    return ordem, frases


def test_as_secoes_da_tela_sao_as_onze_do_despacho_na_ordem_dele():
    """Nome, o que cada uma é em uma linha, e os espaços de cada uma."""
    ordem, _ = _despacho_declarado()
    assert [(s.nome, s.e, s.espacos()) for s in paginas.SECOES] == ordem


def test_a_frase_que_explica_cada_espaco_e_a_do_despacho():
    """Palavra por palavra. Ele não vai ler manual: o manual é a tela."""
    _, frases = _despacho_declarado()
    da_tela = {
        f"{secao.nome}.{espaco.nome}": espaco.explicacao
        for secao in paginas.SECOES
        for espaco in secao.espacos_do_formulario
    }
    assert da_tela == frases


def test_nenhum_espaco_proibido_pela_ferramenta_74_existe_na_tela():
    """`ancora_de_preco` saiu da especificação e não volta por descuido.

    Um campo é um convite a preencher, e um convite a preencher a âncora seria
    a própria tela pedindo o que a lei dele proíbe.
    """
    todos = {e.nome for s in paginas.SECOES for e in s.espacos_do_formulario}
    for proibido in ("ancora_de_preco", "valor_riscado", "prazo", "garantia_prazo"):
        assert proibido not in todos


# ---------------------------------------------------------------------------
# 2. A sentinela da ferramenta 74
# ---------------------------------------------------------------------------
def test_a_sentinela_aponta_valor_riscado():
    achados = paginas.sentinela({"oferta": {"preco_texto": "De R$ 1.997 por R$ 497"}})
    assert [a["padrao"] for a in achados] == ["valor riscado"]
    assert achados[0]["onde"] == "oferta.preco_texto"


def test_a_sentinela_aponta_promessa_de_prazo():
    achados = paginas.sentinela(
        {"cubo": {"subheadline": "Em 30 dias você vai estar modelando sozinho."}}
    )
    assert [a["padrao"] for a in achados] == ["promessa de renda ou de prazo"]


def test_a_sentinela_deixa_passar_o_texto_limpo():
    """O texto que o próprio despacho recomenda não pode acender alarme."""
    limpo = {
        "cubo": {
            "headline": "Aprenda a modelar peças que passam na conferência.",
            "subheadline": "São 34 encomendas em 3 partes, com uma banca fechando cada parte.",
            "cta_texto": "Quero comprar",
        },
        "tempo": {
            "texto": "Ainda não tenho número de quanto tempo leva, e não vou inventar um."
        },
        "para_quem_nao_serve": {
            "recusa_1": "Não serve para quem quer terminar sem refazer nenhuma peça."
        },
    }
    assert paginas.sentinela(limpo) == []


def test_a_sentinela_aponta_os_cinco_padroes_que_ele_escreveu_e_nada_alem():
    """Cinco, os da ferramenta 74. Padrão inventado por agente não entra."""
    assert [p.nome for p in paginas.PADROES_PROIBIDOS] == [
        "contagem regressiva",
        "últimas vagas",
        "valor riscado",
        "promessa de renda ou de prazo",
        "superlativo",
    ]


@respx.mock
def test_a_tela_mostra_o_que_a_sentinela_achou_antes_de_ele_publicar():
    _com_rascunho(
        [
            {
                "nome": "oferta",
                "ordem": 8,
                "slots": {"preco_texto": "De R$ 1.997 por R$ 497"},
            }
        ]
    )
    corpo = _texto(_dentro().get(reverse("pagina_de_venda")))
    # O ACHADO renderizado, e não as palavras soltas: "valor riscado" também
    # está no parágrafo que explica a regra, e "oferta.preco_texto" é o rótulo
    # de um campo do formulário. Medir as duas soltas deixaria este guarda
    # verde com a lista de achados apagada do template, e foi o que a prova por
    # mutação pegou.
    assert "<b>valor riscado</b> em oferta.preco_texto" in corpo
    assert escape("De R$ 1.997 por R$ 497") in corpo


@respx.mock
def test_sem_achado_a_tela_nao_mostra_o_cartao_da_sentinela():
    """Alarme que aparece sempre é alarme que ele aprende a não ler."""
    _com_rascunho(
        [{"nome": "cubo", "ordem": 0, "slots": {"headline": "Peças que passam."}}]
    )
    corpo = _texto(_dentro().get(reverse("pagina_de_venda")))
    assert "A sua regra de 05/09/2026 apontou isto" not in corpo


@respx.mock
def test_a_sentinela_avisa_e_nao_impede_a_publicacao():
    """Quem decide publicar é ele. A regra é dele, e vê-la aplicada não é
    o mesmo que ser impedido por ela."""
    _com_rascunho(
        [
            {
                "nome": "oferta",
                "ordem": 8,
                "slots": {"preco_texto": "De R$ 1.997 por R$ 497"},
            }
        ]
    )
    publicar = respx.post(PUBLICAR).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "11111111-1111-1111-1111-111111111111",
                "site_id": SITE_ID,
                "slug": "oferta",
                "version": 1,
                "offer_slug": "",
                "published_at": "2026-09-19T12:00:00Z",
                "secoes": [],
            },
        )
    )
    resposta = _dentro().post(reverse("pagina_de_venda_publicar"))
    assert resposta.status_code == 302
    assert publicar.called


# ---------------------------------------------------------------------------
# 3. Os estados: cada um com o que aconteceu E o que fazer
# ---------------------------------------------------------------------------
@respx.mock
def test_primeira_vez_e_folha_em_branco_e_nao_erro():
    """404 no rascunho é 'ele nunca escreveu aqui', não falha."""
    _folha_em_branco()
    resposta = _dentro().get(reverse("pagina_de_venda"))
    assert resposta.status_code == 200
    corpo = _texto(resposta)
    assert "nunca esteve no ar" in corpo
    assert 'name="cubo.headline"' in corpo
    assert "não consegui perguntar" not in corpo


@respx.mock
def test_catalogo_fora_do_ar_abre_a_tela_dizendo_o_que_fazer():
    """Fail-OPEN, como a tela do menu: sem catálogo, aviso honesto, nunca 500.
    E sem formulário, porque um formulário que não tem onde salvar é uma
    armadilha de trabalho perdido."""
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(503)
    )
    resposta = _dentro().get(reverse("pagina_de_venda"))
    assert resposta.status_code == 200
    corpo = _texto(resposta)
    assert "não consegui falar com o catálogo" in corpo
    assert 'name="cubo.headline"' not in corpo


@respx.mock
def test_rascunho_que_nao_responde_nao_vira_folha_em_branco():
    """Distinguir 'nunca escreveu' de 'não consegui perguntar' é o que impede a
    tela de oferecer campos vazios que, ao salvar, apagariam o texto dele."""
    _site()
    respx.get(RASCUNHO).mock(return_value=httpx.Response(500))
    corpo = _texto(_dentro().get(reverse("pagina_de_venda")))
    assert "Não consegui ler o que você já escreveu" in corpo
    assert 'name="cubo.headline"' not in corpo


@respx.mock
def test_publicar_rascunho_vazio_diz_o_que_fazer():
    _com_rascunho([])
    respx.post(PUBLICAR).mock(
        return_value=httpx.Response(409, json={"detail": "o rascunho está vazio"})
    )
    resposta = _dentro().post(reverse("pagina_de_venda_publicar"))
    assert resposta.status_code == 409
    corpo = _texto(resposta)
    assert "Não publiquei" in corpo
    assert "escreva pelo menos um espaço" in corpo


@respx.mock
def test_texto_recusado_pelo_vocabulario_mostra_a_frase_do_catalogo():
    _com_rascunho([])
    respx.put(RASCUNHO).mock(
        return_value=httpx.Response(
            422, json={"detail": "slot desconhecido na seção 'cubo'"}
        )
    )
    resposta = _dentro().post(
        reverse("pagina_de_venda_salvar"), {"cubo.headline": "Uma frase"}
    )
    assert resposta.status_code == 422
    # Escapada, como todo texto de fora sai num template: o que se mede é o que
    # chega ao navegador dele, não a string que o catálogo mandou.
    assert escape("slot desconhecido na seção 'cubo'") in _texto(resposta)


@respx.mock
def test_salvamento_que_falhou_devolve_o_que_ele_digitou():
    """O guarda mais importante desta tela. Perder o texto dele por causa de
    uma falha de rede seria a máquina apagando trabalho de gente."""
    _com_rascunho([])
    respx.put(RASCUNHO).mock(return_value=httpx.Response(503))
    resposta = _dentro().post(
        reverse("pagina_de_venda_salvar"),
        {"cubo.headline": "A frase que eu acabei de escrever"},
    )
    assert resposta.status_code == 503
    corpo = _texto(resposta)
    assert "A frase que eu acabei de escrever" in corpo
    assert "Nada do que você escreveu se perdeu" in corpo


# ---------------------------------------------------------------------------
# 4. O que a tela diz sem ele precisar contar
# ---------------------------------------------------------------------------
@respx.mock
def test_a_tela_conta_quantos_espacos_estao_preenchidos():
    _com_rascunho(
        [
            {
                "nome": "cubo",
                "ordem": 0,
                "slots": {"headline": "Uma frase", "cta_texto": "Comprar"},
            }
        ]
    )
    corpo = _texto(_dentro().get(reverse("pagina_de_venda")))
    total = sum(len(s.espacos()) for s in paginas.SECOES)
    assert f"2 de {total}" in corpo


@respx.mock
def test_a_tela_diz_quais_secoes_ficarao_invisiveis_e_que_isso_e_legitimo():
    _com_rascunho([{"nome": "cubo", "ordem": 0, "slots": {"headline": "Uma frase"}}])
    corpo = _texto(_dentro().get(reverse("pagina_de_venda")))
    assert "não vão aparecer" in corpo
    assert "os três vilões" in corpo
    assert "Espaço em branco é resposta legítima" in corpo


@respx.mock
def test_a_tela_explica_a_diferenca_entre_salvar_e_publicar():
    _folha_em_branco()
    corpo = _texto(_dentro().get(reverse("pagina_de_venda")))
    assert "Salvar guarda o texto aqui e não muda o site" in corpo
    assert "Publicar põe no ar" in corpo


@respx.mock
def test_a_tela_traz_um_campo_por_espaco_de_cada_secao():
    _folha_em_branco()
    corpo = _texto(_dentro().get(reverse("pagina_de_venda")))
    for secao in paginas.SECOES:
        for espaco in secao.espacos_do_formulario:
            assert f'name="{secao.nome}.{espaco.nome}"' in corpo


# ---------------------------------------------------------------------------
# 5. A gravação
# ---------------------------------------------------------------------------
@respx.mock
def test_salvar_manda_ao_catalogo_so_o_que_tem_texto_na_ordem_canonica():
    _com_rascunho([])
    gravar = respx.put(RASCUNHO).mock(
        return_value=httpx.Response(200, json=_corpo_do_rascunho([]))
    )
    _dentro().post(
        reverse("pagina_de_venda_salvar"),
        {
            "oferta.preco_texto": "R$ 497",
            "cubo.headline": "Uma frase",
            "cubo.subheadline": "   ",
            "carta.assinatura": "",
        },
    )
    enviado = json.loads(gravar.calls.last.request.content)["secoes"]
    assert enviado == [
        {"nome": "cubo", "ordem": 0, "slots": {"headline": "Uma frase"}},
        {"nome": "oferta", "ordem": 8, "slots": {"preco_texto": "R$ 497"}},
    ]


@respx.mock
def test_salvar_nao_publica_nada():
    _com_rascunho([])
    respx.put(RASCUNHO).mock(
        return_value=httpx.Response(200, json=_corpo_do_rascunho([]))
    )
    publicar = respx.post(PUBLICAR).mock(return_value=httpx.Response(200, json={}))
    _dentro().post(reverse("pagina_de_venda_salvar"), {"cubo.headline": "Uma frase"})
    assert not publicar.called


@respx.mock
@pytest.mark.django_db
def test_salvar_deixa_linha_de_auditoria():
    _com_rascunho([])
    respx.put(RASCUNHO).mock(
        return_value=httpx.Response(200, json=_corpo_do_rascunho([]))
    )
    _dentro().post(reverse("pagina_de_venda_salvar"), {"cubo.headline": "Uma frase"})
    linha = Registro.objects.latest("id")
    assert linha.acao == Registro.SALVAR_RASCUNHO_DA_PAGINA
    assert linha.desfecho == Registro.OK
    assert linha.quem_email == DONO


@respx.mock
@pytest.mark.django_db
def test_a_gravacao_que_falhou_tambem_deixa_linha_de_auditoria():
    """A tentativa que falhou é justamente a que nada mais registra."""
    _com_rascunho([])
    respx.put(RASCUNHO).mock(return_value=httpx.Response(503))
    _dentro().post(reverse("pagina_de_venda_salvar"), {"cubo.headline": "Uma frase"})
    assert Registro.objects.latest("id").desfecho == Registro.NAO_RESPONDEU


@respx.mock
@pytest.mark.django_db
def test_publicar_deixa_linha_de_auditoria_com_a_versao():
    _com_rascunho([{"nome": "cubo", "ordem": 0, "slots": {"headline": "Uma frase"}}])
    respx.post(PUBLICAR).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "11111111-1111-1111-1111-111111111111",
                "site_id": SITE_ID,
                "slug": "oferta",
                "version": 3,
                "offer_slug": "",
                "published_at": "2026-09-19T12:00:00Z",
                "secoes": [],
            },
        )
    )
    _dentro().post(reverse("pagina_de_venda_publicar"))
    linha = Registro.objects.latest("id")
    assert linha.acao == Registro.PUBLICAR_PAGINA
    assert "3" in linha.detalhe


# ---------------------------------------------------------------------------
# 6. A porta
# ---------------------------------------------------------------------------
@respx.mock
def test_sem_cracha_a_tela_nao_abre():
    assert Client().get(reverse("pagina_de_venda")).status_code in (302, 404)


@respx.mock
def test_sem_cracha_nenhum_gesto_escreve():
    _site()
    gravar = respx.put(RASCUNHO).mock(return_value=httpx.Response(200, json={}))
    publicar = respx.post(PUBLICAR).mock(return_value=httpx.Response(200, json={}))
    assert Client().post(
        reverse("pagina_de_venda_salvar"), {"cubo.headline": "Invasor"}
    ).status_code in (302, 404)
    assert Client().post(reverse("pagina_de_venda_publicar")).status_code in (302, 404)
    assert not gravar.called
    assert not publicar.called


# ---------------------------------------------------------------------------
# 7. Ela é alcançável pelo menu do bastidor
# ---------------------------------------------------------------------------
def test_a_tela_esta_no_menu_do_admin():
    """Tela que ele não acha é tela que não existe."""
    from apps.core import moldura

    assert ("pagina_de_venda", "Página de venda") in moldura.SECOES
