# tests/test_mobile_first_contract.py  # [RECEITA:R5 v1]
# Mobile-first é contrato desta célula (DESPACHO funil/vitrine), não escolha de
# estilo: toda página pública precisa estender templates/base_mobile.html, o que
# nesta plataforma quer dizer, na prática, três coisas mensuráveis no HTML
# servido — nenhuma delas depende de renderizar JS num browser real:
#   1. viewport mobile puro (sem largura fixa nem "user-scalable=no");
#   2. layout fluido: o container raiz usa max-width relativo (rem), não px;
#   3. nenhum <meta viewport> concorrente vazando de outro lugar.
import re

from tests.conftest import HOST_A

VIEWPORT_MOBILE = '<meta name="viewport" content="width=device-width, initial-scale=1">'


def test_viewport_mobile_first_esta_presente_e_e_unico(client, rede):
    resp = client.get("/", HTTP_HOST=HOST_A)
    corpo = resp.content.decode()
    assert corpo.count(VIEWPORT_MOBILE.encode().decode()) == 1
    assert "width=device-width" in corpo
    assert "user-scalable=no" not in corpo
    assert not re.search(r'<meta name="viewport" content="width=\d', corpo)


def test_container_raiz_e_fluido_nao_pixel_fixo(client, rede):
    resp = client.get("/", HTTP_HOST=HOST_A)
    corpo = resp.content.decode()
    assert re.search(r"\.wrap\s*\{[^}]*max-width:\s*\d+rem", corpo)
    assert not re.search(r"\.wrap\s*\{[^}]*width:\s*\d+px", corpo)
