"""F8b: a página de oferta sorteia o braço do experimento ativo e o mede.

O catálogo manda o `experimento_ativo` da página (F8c), o sorteio decide o
braço de cada visitante (F8a) e esta página junta os dois. Cinco leis se
medem aqui:

1. **O visitante vê o texto do braço dele**, no slot em teste, e o elemento
   desse slot carrega `data-experimento-id` e `data-variante-id`, os nomes que
   o ensaio L10 (`e2e/ensaio_experimento.js`) lê.
2. **O braço é do visitante, não da visita.** O mesmo `visitor_id` cai sempre
   no mesmo braço, sem nada guardado no servidor.
3. **Experimento com defeito não derruba a vitrine.** A página sai como foi
   publicada, sem marca e sem par nos eventos.
4. **O par viaja só no que o servidor assinou.** `pagina-vista` e os fatos do
   contexto assinado levam `experimento_id` e `variante_id` juntos; o corpo que
   o navegador escreve não os carrega.
5. **Página com braço não vai para cache nenhum.** Um cache compartilhado
   serviria o braço de uma pessoa a outra e trocaria gente de braço no meio da
   medição.
"""

import hashlib
import json
import re

import httpx
import pytest

from apps.core.visitante import COOKIE
from tests.conftest import CATALOGO, HOST_A, SITE_A
from tests.test_pagina_de_oferta import CAMINHO, SECOES_CHEIAS, pagina, publicar
from tests.test_telemetria_do_navegador import (
    clique,
    contexto_da_tela,
    enviar,
    fatos,
    fio,  # noqa: F401 - fixture
    postar_lead,
    secao_vista,
    validar_contra_o_contrato,
)

EXPERIMENTO_ID = "0b6f1c3e-8a52-4d7e-9f10-2c4b6d8e0a13"

#: Dois visitantes, um em cada braço do 50/50 pela fórmula do contrato. O
#: primeiro teste confere isso contra a fórmula escrita aqui, e não contra o
#: código que a implementa.
NO_BRACO_A = "7c9e2a41-5b3d-4f86-a1e0-9d2c4b6e8f17"
NO_BRACO_B = "3f2b9c4e-1a5d-4e77-9b02-8c1d6f5a4b30"

TEXTO_PUBLICADO = "Construa o seu primeiro esqueleto"
TEXTO_B = "Monte o esqueleto inteiro em doze semanas"


def publicado(secao: str, slot: str) -> str:
    return next(s for s in SECOES_CHEIAS if s["nome"] == secao)["slots"][slot]


def experimento(secao="cubo", slot="headline", texto_b=TEXTO_B):
    return {
        "id": EXPERIMENTO_ID,
        "secao": secao,
        "slot": slot,
        "variantes": [
            {"variante_id": "a", "peso": 5000, "valor": publicado(secao, slot)},
            {"variante_id": "b", "peso": 5000, "valor": texto_b},
        ],
    }


def abrir_com(client, rede, ativo, visitante=None):
    if visitante:
        client.cookies[COOKIE] = visitante
    publicar(rede, {**pagina(SECOES_CHEIAS), "experimento_ativo": ativo})
    return client.get(CAMINHO, HTTP_HOST=HOST_A)


def marca(variante_id: str) -> str:
    return f'data-experimento-id="{EXPERIMENTO_ID}" data-variante-id="{variante_id}"'


def elemento_marcado(corpo: str) -> tuple[str, str]:
    """A tag que carrega a marca e o que vem logo depois dela."""
    marcadas = [
        achado
        for achado in re.finditer(r"<[a-z0-9]+\b[^>]*>", corpo)
        if "data-experimento-id=" in achado.group(0)
    ]
    assert len(marcadas) == 1, f"{len(marcadas)} elementos marcados, esperava 1"
    return marcadas[0].group(0), corpo[marcadas[0].end() :]


# ------------------------------------------------------ o braço na tela


def test_os_visitantes_de_teste_caem_onde_a_formula_do_contrato_manda():
    def balde(visitante):
        resumo = hashlib.sha256(f"{EXPERIMENTO_ID}:{visitante}".encode()).hexdigest()
        return int(resumo[:8], 16) % 10000

    assert balde(NO_BRACO_A) < 5000 <= balde(NO_BRACO_B)


def test_quem_cai_em_b_ve_o_texto_b_no_slot_marcado(client, rede):
    resp = abrir_com(client, rede, experimento(), NO_BRACO_B)
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert f"<h1 {marca('b')}>{TEXTO_B}</h1>" in corpo
    assert TEXTO_PUBLICADO not in corpo, "o texto do braço a vazou para quem está em b"


def test_quem_cai_em_a_ve_o_texto_publicado_marcado_como_a(client, rede):
    corpo = abrir_com(client, rede, experimento(), NO_BRACO_A).content.decode()
    assert f"<h1 {marca('a')}>{TEXTO_PUBLICADO}</h1>" in corpo
    assert TEXTO_B not in corpo


@pytest.mark.parametrize(
    "secao, slot",
    [
        ("cubo", "headline"),
        ("cubo", "subheadline"),
        ("cubo", "cta_texto"),
        ("cubo", "imagem"),
        ("viloes", "headline"),
        ("viloes", "vilao_2"),
        ("viloes", "prova"),
        ("metodo", "texto"),
        ("metodo", "imagem"),
        ("para_quem_nao_serve", "recusa_3"),
        ("oferta", "headline"),
        ("oferta", "o_que_recebe"),
        ("oferta", "preco_texto"),
        ("oferta", "parcelamento"),
        ("oferta", "cta_texto"),
        ("carta", "assinatura"),
    ],
)
def test_o_elemento_marcado_e_o_do_slot_e_mostra_o_texto_do_braco(
    client, rede, secao, slot
):
    texto_b = (
        "https://exemplo.invalido/braco-b.png"
        if slot == "imagem"
        else f"Texto do braco b em {secao} {slot}"
    )
    corpo = abrir_com(
        client, rede, experimento(secao, slot, texto_b), NO_BRACO_B
    ).content.decode()
    tag, depois = elemento_marcado(corpo)
    assert marca("b") in tag
    if slot == "imagem":
        assert f'src="{texto_b}"' in tag
    else:
        assert depois.startswith(texto_b), f"a marca está em {tag}, longe do slot"
    assert publicado(secao, slot) not in corpo


# -------------------------------------------------------------- sticky


def test_o_mesmo_visitante_ve_sempre_o_mesmo_braco(client, rede):
    for _ in range(3):
        corpo = abrir_com(client, rede, experimento(), NO_BRACO_B).content.decode()
        assert marca("b") in corpo


def test_quem_chega_sem_cookie_volta_no_mesmo_braco(client, rede):
    primeira = abrir_com(client, rede, experimento())
    visitante = primeira.cookies[COOKIE].value
    braco = re.search(r'data-variante-id="([a-z])"', primeira.content.decode())
    assert braco, "a primeira visita não mostrou braço nenhum"
    segunda = client.get(CAMINHO, HTTP_HOST=HOST_A)
    assert COOKIE not in segunda.cookies, "a volta ganhou um visitante novo"
    assert client.cookies[COOKIE].value == visitante
    assert f'data-variante-id="{braco.group(1)}"' in segunda.content.decode()


# ------------------------------------------------------------ fail-open


def test_sem_experimento_a_pagina_e_a_de_sempre_e_segue_guardavel(client, rede):
    resp = abrir_com(client, rede, None, NO_BRACO_B)
    corpo = resp.content.decode()
    assert resp.status_code == 200
    assert f"<h1>{TEXTO_PUBLICADO}</h1>" in corpo
    assert "data-experimento-id" not in corpo and "data-variante-id" not in corpo
    assert "no-store" not in resp.get("Cache-Control", "")


def test_experimento_fora_de_forma_mostra_a_versao_publicada(client, rede):
    torto = experimento()
    torto["variantes"][1]["peso"] = 4000
    resp = abrir_com(client, rede, torto, NO_BRACO_B)
    corpo = resp.content.decode()
    assert resp.status_code == 200
    assert f"<h1>{TEXTO_PUBLICADO}</h1>" in corpo
    assert "data-experimento-id" not in corpo
    assert "no-store" not in resp.get("Cache-Control", "")


def test_experimento_numa_secao_que_a_pagina_nao_desenha_nao_mede_nada(
    client, rede, fio, caplog
):
    fantasma = experimento()
    fantasma["secao"] = "garantia"
    resp = abrir_com(client, rede, fantasma, NO_BRACO_B)
    corpo = resp.content.decode()
    assert resp.status_code == 200
    assert f"<h1>{TEXTO_PUBLICADO}</h1>" in corpo
    assert "data-experimento-id" not in corpo
    assert "no-store" not in resp.get("Cache-Control", "")
    [visita] = fatos(fio, "funil.pagina-vista")
    assert "experimento_id" not in visita["data"]
    assert "variante_id" not in visita["data"]
    assert "garantia" in caplog.text, "o defeito do catálogo sumiu sem log"


def test_catalogo_fora_do_ar_e_a_tela_de_sempre_sem_braco(client, rede):
    rede.get(f"{CATALOGO}/sites/{SITE_A['id']}/paginas/oferta").mock(
        side_effect=httpx.ConnectError("catálogo fora do ar")
    )
    resp = client.get(CAMINHO, HTTP_HOST=HOST_A)
    assert resp.status_code == 503
    assert "data-experimento-id" not in resp.content.decode()


# -------------------------------------------------------------- cache


def test_pagina_com_braco_nao_e_guardada_por_ninguem(client, rede):
    resp = abrir_com(client, rede, experimento(), NO_BRACO_B)
    assert resp["Cache-Control"] == "private, no-store"


# ------------------------------------------------ o par nos eventos


def test_pagina_vista_leva_o_par_do_braco(client, rede, fio):
    abrir_com(client, rede, experimento(), NO_BRACO_B)
    [visita] = fatos(fio, "funil.pagina-vista")
    validar_contra_o_contrato(visita)
    assert visita["data"]["experimento_id"] == EXPERIMENTO_ID
    assert visita["data"]["variante_id"] == "b"


def test_pagina_vista_sem_experimento_nao_leva_nenhum_dos_dois(client, rede, fio):
    abrir_com(client, rede, None, NO_BRACO_B)
    [visita] = fatos(fio, "funil.pagina-vista")
    assert "experimento_id" not in visita["data"]
    assert "variante_id" not in visita["data"]


@pytest.fixture
def tela_com_braco(client, rede, fio):
    """A oferta aberta por quem está no braço b, e o contexto assinado dela."""
    resp = abrir_com(client, rede, experimento(), NO_BRACO_B)
    fio.escritas.clear()
    return contexto_da_tela(resp)


def test_a_exposicao_e_a_secao_vista_da_secao_do_slot_com_o_par(
    client, tela_com_braco, fio
):
    assert enviar(client, secao_vista(tela_com_braco, "cubo")).status_code == 204
    [exposicao] = fatos(fio, "funil.secao-vista")
    validar_contra_o_contrato(exposicao)
    assert exposicao["data"]["secao"] == "cubo"
    assert exposicao["data"]["experimento_id"] == EXPERIMENTO_ID
    assert exposicao["data"]["variante_id"] == "b"


def test_o_clique_para_o_checkout_leva_o_par(client, tela_com_braco, fio):
    assert enviar(client, clique(tela_com_braco)).status_code == 204
    [envelope] = fatos(fio, "funil.cta-clicado")
    validar_contra_o_contrato(envelope)
    assert envelope["data"]["experimento_id"] == EXPERIMENTO_ID
    assert envelope["data"]["variante_id"] == "b"


def test_o_lead_da_pagina_com_braco_leva_o_par(client, tela_com_braco, fio):
    corpo = {"email": "cliente@exemplo.com", "contexto": tela_com_braco}
    assert postar_lead(client, corpo).status_code == 200
    [envelope] = fatos(fio, "funil.lead-capturado")
    validar_contra_o_contrato(envelope)
    assert envelope["data"]["experimento_id"] == EXPERIMENTO_ID
    assert envelope["data"]["variante_id"] == "b"


def test_o_navegador_nao_escreve_o_braco_no_corpo(client, tela_com_braco, fio):
    forjado = {**secao_vista(tela_com_braco, "cubo"), "variante_id": "a"}
    assert enviar(client, forjado).status_code == 400
    assert fio.escritas == []


def test_fato_de_pagina_sem_experimento_nao_leva_o_par(client, rede, fio):
    resp = abrir_com(client, rede, None, NO_BRACO_B)
    fio.escritas.clear()
    enviar(client, secao_vista(contexto_da_tela(resp), "cubo"))
    [envelope] = fatos(fio, "funil.secao-vista")
    assert "experimento_id" not in envelope["data"]
    assert "variante_id" not in envelope["data"]


def test_nenhum_texto_de_variante_viaja_nos_eventos(client, rede, fio):
    resp = abrir_com(client, rede, experimento(), NO_BRACO_B)
    enviar(client, secao_vista(contexto_da_tela(resp), "cubo"))
    cru = json.dumps([campos for _, campos in fio.escritas], ensure_ascii=False)
    assert TEXTO_B not in cru, "o texto da variante vazou para o evento"
