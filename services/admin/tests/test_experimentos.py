"""A tela `/admin/paginas/experimentos/`: criar e conduzir um experimento.

O catálogo é o dono do experimento (frente F5). O catálogo falso aqui é o
`respx`, que atende nos endereços do ciclo que esta tela chama, e é por ele
que se prova, sem rede nenhuma:

1. **A lista mostra cada experimento da página com o estado dele**, e o gesto
   que cabe a cada estado: rascunho inicia ou encerra, ativo só encerra,
   encerrado não tem gesto (retomar é criar outro).
2. **O braço `a` é o texto que está no ar**, lido da página publicada no momento
   de salvar, nunca do formulário.
3. **O formulário recusa antes de perguntar ao catálogo** o que não faz
   sentido: texto novo vazio, espaço fora do vocabulário, alocação fora de 1 a
   99, taxa base ou efeito mínimo impossíveis, dias que não são inteiro
   positivo. E volta com o que ele digitou.
4. **Duplo clique no iniciar não duplica**: a segunda resposta do catálogo
   (409, porque já está ativo) vira o mesmo recado de sucesso, sem segunda
   linha de auditoria.
5. **409 de verdade** (outro experimento ocupa a página) diz com todas as
   letras que já existe um experimento ativo nesta página.
6. **Catálogo fora** diz o que houve e o que fazer, e nunca vira 500.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils.html import escape

from apps.auditoria.models import Registro
from apps.core.resultado_do_experimento import n_por_braco_planejado

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
SITE_ID = "site-mesh"
PAGINA = f"{CATALOGO}/sites/{SITE_ID}/paginas/oferta"
EXPERIMENTOS = f"{PAGINA}/experimentos"
UM_EXPERIMENTO = f"{CATALOGO}/experimentos"
ID_RASCUNHO = "0b6f3c1e-5d1a-4a0e-9d61-3f1c2b7a9e01"
ID_ATIVO = "7c2d9e4f-1a3b-4c5d-8e6f-9a0b1c2d3e4f"
ID_ENCERRADO = "1f2e3d4c-5b6a-4978-8a9b-0c1d2e3f4a5b"

SITE = {"id": SITE_ID, "host": "testserver", "name": "Meshcraft", "active": True}
TITULO_NO_AR = "Modele para imprimir, do primeiro cubo à peça vendida"


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


def _no_ar(slots_do_cubo=None):
    """A página publicada, que é de onde sai o braço `a`."""
    respx.get(PAGINA).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "versao-3",
                "site_id": SITE_ID,
                "slug": "oferta",
                "version": 3,
                "published_at": "2026-09-20T12:00:00Z",
                "secoes": [
                    {
                        "nome": "cubo",
                        "ordem": 0,
                        "slots": (
                            {"headline": TITULO_NO_AR}
                            if slots_do_cubo is None
                            else slots_do_cubo
                        ),
                    }
                ],
            },
        )
    )


def _experimento(estado, experimento_id, **mais) -> dict:
    corpo = {
        "id": experimento_id,
        "secao": "cubo",
        "slot": "headline",
        "hipotese": "Falar de peça vendida leva mais gente ao checkout.",
        "estado": estado,
        "metrica_principal": "cta_checkout",
        "taxa_base": 0.1,
        "mde": 0.03,
        "n_por_braco_planejado": 1600,
        "dias_planejados": 21,
        "criado_em": "2026-09-26T10:00:00Z",
        "iniciado_em": None,
        "fim_planejado": None,
        "variantes": [
            {"variante_id": "a", "peso": 5000, "valor": TITULO_NO_AR},
            {"variante_id": "b", "peso": 5000, "valor": "Da primeira peça à venda"},
        ],
    }
    corpo.update(mais)
    return corpo


def _lista(*experimentos):
    respx.get(EXPERIMENTOS).mock(
        return_value=httpx.Response(200, json={"experimentos": list(experimentos)})
    )


def _texto(resposta) -> str:
    return resposta.content.decode()


def _formulario(**troca) -> dict:
    campos = {
        "espaco": "cubo.headline",
        "hipotese": "Falar de peça vendida leva mais gente ao checkout.",
        "texto_b": "Da primeira peça à venda, sem adivinhar medida",
        "parte_b": "50",
        "metrica_principal": "cta_checkout",
        "taxa_base": "10",
        "mde": "3",
        "dias_planejados": "21",
        "gesto": "salvar",
    }
    campos.update(troca)
    return campos


# ---------------------------------------------------------------------------
# 1. A lista da página
# ---------------------------------------------------------------------------
@respx.mock
def test_a_lista_mostra_cada_experimento_com_o_estado_e_o_gesto_que_cabe():
    _site()
    _lista(
        _experimento("rascunho", ID_RASCUNHO),
        _experimento("encerrado", ID_ENCERRADO, iniciado_em="2026-09-01T10:00:00Z"),
    )
    resposta = _dentro().get(reverse("experimentos"))
    assert resposta.status_code == 200
    corpo = _texto(resposta)
    assert "Falar de peça vendida leva mais gente ao checkout." in corpo
    assert "cubo.headline" in corpo
    assert "Rascunho" in corpo and "Encerrado" in corpo
    assert f'form="iniciar-{ID_RASCUNHO}"' in corpo
    assert reverse("experimento_iniciar", args=[ID_RASCUNHO]) in corpo
    assert reverse("experimento_encerrar", args=[ID_RASCUNHO]) in corpo
    assert reverse("experimento_iniciar", args=[ID_ENCERRADO]) not in corpo
    assert reverse("experimento_encerrar", args=[ID_ENCERRADO]) not in corpo
    assert reverse("experimento_novo") in corpo


@respx.mock
def test_com_um_ativo_o_rascunho_nao_oferece_iniciar_e_diz_por_que():
    _site()
    _lista(
        _experimento("ativo", ID_ATIVO, iniciado_em="2026-09-20T10:00:00Z"),
        _experimento("rascunho", ID_RASCUNHO),
    )
    corpo = _texto(_dentro().get(reverse("experimentos")))
    assert reverse("experimento_iniciar", args=[ID_RASCUNHO]) not in corpo
    assert f'form="iniciar-{ID_RASCUNHO}"' not in corpo
    assert reverse("experimento_encerrar", args=[ID_ATIVO]) in corpo
    assert "encerre o que está no ar" in corpo


@respx.mock
def test_encerrado_explica_que_retomar_e_criar_um_experimento_novo():
    _site()
    _lista(_experimento("encerrado", ID_ENCERRADO))
    corpo = _texto(_dentro().get(reverse("experimentos")))
    assert "crie um experimento novo" in corpo


@respx.mock
def test_lista_vazia_e_primeiro_uso_e_nao_erro():
    _site()
    _lista()
    resposta = _dentro().get(reverse("experimentos"))
    assert resposta.status_code == 200
    corpo = _texto(resposta)
    assert "Nenhum experimento nesta página ainda" in corpo
    assert reverse("experimento_novo") in corpo


@respx.mock
def test_catalogo_fora_do_ar_diz_o_que_houve_e_o_que_fazer():
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(503)
    )
    resposta = _dentro().get(reverse("experimentos"))
    assert resposta.status_code == 200
    corpo = _texto(resposta)
    assert "não consegui falar com o catálogo" in corpo
    assert "Tente de novo daqui a pouco" in corpo


@respx.mock
def test_formulario_sem_catalogo_nao_abre_campo_que_nao_tem_onde_salvar():
    respx.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(503)
    )
    corpo = _texto(_dentro().get(reverse("experimento_novo")))
    assert "não consegui falar com o catálogo" in corpo
    assert 'name="hipotese"' not in corpo


@respx.mock
def test_lista_que_nao_responde_nao_vira_lista_vazia():
    _site()
    respx.get(EXPERIMENTOS).mock(return_value=httpx.Response(500))
    corpo = _texto(_dentro().get(reverse("experimentos")))
    assert "Não consegui ler os experimentos" in corpo
    assert "Nenhum experimento nesta página ainda" not in corpo


# ---------------------------------------------------------------------------
# 2. O formulário do experimento novo
# ---------------------------------------------------------------------------
@respx.mock
def test_o_formulario_mostra_o_texto_no_ar_como_braco_a():
    _site()
    _no_ar()
    resposta = _dentro().get(reverse("experimento_novo"))
    assert resposta.status_code == 200
    corpo = _texto(resposta)
    assert escape(TITULO_NO_AR) in corpo
    assert 'name="texto_b"' in corpo
    assert 'value="cubo.headline" selected' in corpo
    assert 'name="parte_b" value="50"' in corpo
    assert "Entrada no checkout" in corpo


@respx.mock
def test_copiar_o_texto_atual_prepara_um_teste_a_a():
    _site()
    _no_ar()
    corpo = _texto(
        _dentro().get(
            reverse("experimento_novo"), {"espaco": "cubo.headline", "copiar": "1"}
        )
    )
    assert f">{escape(TITULO_NO_AR)}</textarea>" in corpo


@respx.mock
def test_espaco_vazio_no_ar_nao_vira_braco_a():
    _site()
    _no_ar(slots_do_cubo={"subheadline": "Outra frase"})
    corpo = _texto(_dentro().get(reverse("experimento_novo")))
    assert "está vazio na página que está no ar" in corpo
    assert 'value="salvar"' not in corpo


@respx.mock
def test_pagina_que_nunca_foi_ao_ar_nao_tem_o_que_testar():
    _site()
    respx.get(PAGINA).mock(
        return_value=httpx.Response(404, json={"detail": "sem versão publicada"})
    )
    corpo = _texto(_dentro().get(reverse("experimento_novo")))
    assert "ainda não está no ar" in corpo
    assert 'value="salvar"' not in corpo


@respx.mock
def test_calcular_mostra_a_amostra_planejada_sem_gravar_nada():
    _site()
    _no_ar()
    criar = respx.post(EXPERIMENTOS).mock(return_value=httpx.Response(201, json={}))
    resposta = _dentro().post(
        reverse("experimento_novo"), _formulario(gesto="calcular")
    )
    assert resposta.status_code == 200
    esperado = n_por_braco_planejado(0.1, 0.03)
    assert f"{esperado:,}".replace(",", ".") in _texto(resposta)
    assert not criar.called


# ---------------------------------------------------------------------------
# 3. Salvar em rascunho
# ---------------------------------------------------------------------------
@respx.mock
def test_salvar_cria_o_rascunho_com_o_texto_no_ar_como_braco_a():
    _site()
    _no_ar()
    criar = respx.post(EXPERIMENTOS).mock(
        return_value=httpx.Response(201, json=_experimento("rascunho", ID_RASCUNHO))
    )
    resposta = _dentro().post(
        reverse("experimento_novo"),
        # O braço `a` do formulário é ignorado: a verdade é a página no ar.
        _formulario(texto_a="texto forjado", parte_b="30"),
    )
    assert resposta.status_code == 302
    assert resposta["Location"].endswith(f"{reverse('experimentos')}?recado=criado")
    enviado = json.loads(criar.calls.last.request.content)
    assert enviado == {
        "secao": "cubo",
        "slot": "headline",
        "hipotese": "Falar de peça vendida leva mais gente ao checkout.",
        "metrica_principal": "cta_checkout",
        "taxa_base": 0.1,
        "mde": 0.03,
        "n_por_braco_planejado": n_por_braco_planejado(0.1, 0.03),
        "dias_planejados": 21,
        "variantes": [
            {"variante_id": "a", "peso": 7000, "valor": TITULO_NO_AR},
            {
                "variante_id": "b",
                "peso": 3000,
                "valor": "Da primeira peça à venda, sem adivinhar medida",
            },
        ],
    }
    linha = Registro.objects.get(acao=Registro.CRIAR_EXPERIMENTO)
    assert linha.desfecho == Registro.OK
    assert linha.alvo == ID_RASCUNHO
    assert "Da primeira" not in linha.detalhe


@pytest.mark.parametrize(
    "troca, frase",
    [
        ({"texto_b": "   "}, "Escreva o texto do braço b"),
        ({"hipotese": ""}, "Escreva a hipótese"),
        ({"espaco": "cubo.nao_existe"}, "não é um espaço da página"),
        ({"parte_b": "0"}, "entre 1 e 99"),
        ({"parte_b": "100"}, "entre 1 e 99"),
        ({"parte_b": "meio"}, "entre 1 e 99"),
        ({"taxa_base": "0"}, "taxa base"),
        ({"taxa_base": "abc"}, "taxa base"),
        ({"mde": "0"}, "efeito mínimo"),
        ({"taxa_base": "90", "mde": "15"}, "passa de 100%"),
        ({"dias_planejados": "0"}, "dias"),
        ({"dias_planejados": "2,5"}, "dias"),
        ({"metrica_principal": "receita"}, "métrica"),
    ],
)
@respx.mock
def test_o_que_nao_faz_sentido_e_recusado_antes_do_catalogo(troca, frase):
    _site()
    _no_ar()
    criar = respx.post(EXPERIMENTOS).mock(return_value=httpx.Response(201, json={}))
    formulario = _formulario(**troca)
    resposta = _dentro().post(reverse("experimento_novo"), formulario)
    assert resposta.status_code == 422
    corpo = _texto(resposta)
    assert escape(frase) in corpo
    assert not criar.called
    if formulario["hipotese"]:
        assert escape(formulario["hipotese"]) in corpo


@respx.mock
def test_criar_com_o_catalogo_fora_devolve_o_que_ele_digitou():
    _site()
    _no_ar()
    respx.post(EXPERIMENTOS).mock(return_value=httpx.Response(503))
    resposta = _dentro().post(reverse("experimento_novo"), _formulario())
    assert resposta.status_code == 503
    corpo = _texto(resposta)
    assert "Não consegui salvar agora" in corpo
    assert "Da primeira peça à venda, sem adivinhar medida" in corpo
    linha = Registro.objects.get(acao=Registro.CRIAR_EXPERIMENTO)
    assert linha.desfecho == Registro.NAO_RESPONDEU


@respx.mock
def test_recusa_do_catalogo_ao_criar_mostra_a_frase_dele():
    _site()
    _no_ar()
    respx.post(EXPERIMENTOS).mock(
        return_value=httpx.Response(
            422, json={"detail": "os pesos precisam somar 10000"}
        )
    )
    resposta = _dentro().post(reverse("experimento_novo"), _formulario())
    assert resposta.status_code == 422
    assert "os pesos precisam somar 10000" in _texto(resposta)


# ---------------------------------------------------------------------------
# 4. Iniciar e encerrar
# ---------------------------------------------------------------------------
def _iniciar(experimento_id=ID_RASCUNHO):
    return respx.post(f"{UM_EXPERIMENTO}/{experimento_id}/iniciar")


def _encerrar(experimento_id=ID_ATIVO):
    return respx.post(f"{UM_EXPERIMENTO}/{experimento_id}/encerrar")


def _um(experimento):
    respx.get(f"{UM_EXPERIMENTO}/{experimento['id']}").mock(
        return_value=httpx.Response(200, json=experimento)
    )


@respx.mock
def test_iniciar_poe_o_experimento_no_ar_e_deixa_linha_de_auditoria():
    _site()
    _iniciar().mock(
        return_value=httpx.Response(200, json=_experimento("ativo", ID_RASCUNHO))
    )
    resposta = _dentro().post(reverse("experimento_iniciar", args=[ID_RASCUNHO]))
    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?recado=iniciado")
    linha = Registro.objects.get(acao=Registro.INICIAR_EXPERIMENTO)
    assert (linha.alvo, linha.desfecho) == (ID_RASCUNHO, Registro.OK)


@respx.mock
def test_duplo_clique_no_iniciar_nao_duplica():
    """O segundo clique chega quando o primeiro já pôs no ar. O catálogo diz
    409; a tela confere o experimento, vê que está ativo e responde o mesmo
    sucesso, sem segunda linha de auditoria e sem aviso de conflito."""
    _site()
    _iniciar().mock(
        side_effect=[
            httpx.Response(200, json=_experimento("ativo", ID_RASCUNHO)),
            httpx.Response(409, json={"detail": "o experimento não está em rascunho"}),
        ]
    )
    _um(_experimento("ativo", ID_RASCUNHO))
    cliente = _dentro()
    primeira = cliente.post(reverse("experimento_iniciar", args=[ID_RASCUNHO]))
    segunda = cliente.post(reverse("experimento_iniciar", args=[ID_RASCUNHO]))
    assert primeira.status_code == segunda.status_code == 302
    assert segunda["Location"].endswith("?recado=iniciado")
    assert Registro.objects.filter(acao=Registro.INICIAR_EXPERIMENTO).count() == 1


@respx.mock
def test_iniciar_com_outro_ativo_diz_que_ja_existe_um_ativo_nesta_pagina():
    _site()
    _iniciar().mock(
        return_value=httpx.Response(
            409, json={"detail": "a página já tem um experimento ativo"}
        )
    )
    _um(_experimento("rascunho", ID_RASCUNHO))
    _lista(
        _experimento("ativo", ID_ATIVO),
        _experimento("rascunho", ID_RASCUNHO),
    )
    resposta = _dentro().post(reverse("experimento_iniciar", args=[ID_RASCUNHO]))
    assert resposta.status_code == 409
    assert "Já existe um experimento ativo nesta página" in _texto(resposta)
    linha = Registro.objects.get(acao=Registro.INICIAR_EXPERIMENTO)
    assert linha.desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
def test_iniciar_com_o_catalogo_fora_diz_que_nada_mudou():
    _site()
    _iniciar().mock(side_effect=httpx.ConnectError("sem rede"))
    _lista(_experimento("rascunho", ID_RASCUNHO))
    resposta = _dentro().post(reverse("experimento_iniciar", args=[ID_RASCUNHO]))
    assert resposta.status_code == 503
    corpo = _texto(resposta)
    assert "Não consegui iniciar agora" in corpo
    assert "Aperte Iniciar de novo" in corpo


@respx.mock
def test_encerrar_manda_a_decisao_encerrar_e_deixa_linha_de_auditoria():
    _site()
    rota = _encerrar().mock(
        return_value=httpx.Response(200, json=_experimento("encerrado", ID_ATIVO))
    )
    resposta = _dentro().post(reverse("experimento_encerrar", args=[ID_ATIVO]))
    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?recado=encerrado")
    assert json.loads(rota.calls.last.request.content) == {"decisao": "encerrar"}
    linha = Registro.objects.get(acao=Registro.ENCERRAR_EXPERIMENTO)
    assert (linha.alvo, linha.desfecho) == (ID_ATIVO, Registro.OK)


@respx.mock
def test_encerrar_duas_vezes_nao_vira_erro():
    _site()
    _encerrar().mock(return_value=httpx.Response(409, json={"detail": "já encerrado"}))
    _um(_experimento("encerrado", ID_ATIVO))
    resposta = _dentro().post(reverse("experimento_encerrar", args=[ID_ATIVO]))
    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?recado=encerrado")
    assert not Registro.objects.filter(acao=Registro.ENCERRAR_EXPERIMENTO).exists()


# ---------------------------------------------------------------------------
# 5. A porta e o caminho até a tela
# ---------------------------------------------------------------------------
@respx.mock
def test_sem_cracha_nada_abre_e_nada_escreve():
    _site()
    criar = respx.post(EXPERIMENTOS).mock(return_value=httpx.Response(201, json={}))
    iniciar = _iniciar().mock(return_value=httpx.Response(200, json={}))
    encerrar = _encerrar().mock(return_value=httpx.Response(200, json={}))
    fora = Client()
    assert fora.get(reverse("experimentos")).status_code in (302, 404)
    assert fora.post(reverse("experimento_novo"), _formulario()).status_code in (
        302,
        404,
    )
    assert fora.post(
        reverse("experimento_iniciar", args=[ID_RASCUNHO])
    ).status_code in (302, 404)
    assert fora.post(reverse("experimento_encerrar", args=[ID_ATIVO])).status_code in (
        302,
        404,
    )
    assert not (criar.called or iniciar.called or encerrar.called)


@respx.mock
def test_a_tela_da_pagina_de_venda_leva_aos_experimentos():
    _site()
    respx.get(f"{PAGINA}/rascunho").mock(
        return_value=httpx.Response(404, json={"detail": "sem rascunho"})
    )
    corpo = _texto(_dentro().get(reverse("pagina_de_venda")))
    assert reverse("experimentos") in corpo
