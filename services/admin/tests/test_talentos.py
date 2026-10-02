"""Rede de talentos: leitura e gravação persistente das contagens."""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import direcao, placar, talentos
from apps.core.models import RegistroDoPlacar

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
ALUNOS_LISTA = f"{ALUNOS}/matriculas"
HOJE = dt.date(2026, 9, 21)

pytestmark = pytest.mark.django_db

TALENTOS = "alunos-selecionados-para-a-rede"
ESTUDIOS = "estudios-parceiros"
ENCAIXES = "encaixes-com-estudio"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr(placar.timezone, "localdate", lambda: HOJE)
    monkeypatch.setattr(talentos.timezone, "localdate", lambda: HOJE)


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


def _a_escola_responde():
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(ALUNOS_LISTA).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "status": "ativa",
                    "origem": "liberado",
                    "criada_em": "2026-09-10T12:00:00-03:00",
                    "virou_aluno_em": "2026-09-11T12:00:00-03:00",
                }
            ],
        )
    )


def _medicao(quando: str, foto: str, arquivo: str = "um-registro") -> dict:
    return {"arquivo": arquivo, "tipo": "medicao", "quando": quando, "foto": foto}


def _passo(laco: dict, chave: str) -> dict:
    return next(p for p in laco["passos"] if p["chave"] == chave)


# ---------------------------------------------------------------------------
# 1. Ausência de contagem nunca vira zero
# ---------------------------------------------------------------------------


def test_nunca_contado_nao_e_zero():
    laco = talentos.montar([], 133, HOJE)

    for chave in ("talentos", "estudios", "encaixes"):
        assert _passo(laco, chave)["estado"] == "nunca-contado"
        assert _passo(laco, chave)["valor"] is None
    assert laco["nunca_contadas"] == 3


def test_livro_ausente_e_outra_coisa_de_nenhuma_contagem():
    laco = talentos.montar(None, 133, HOJE)

    assert laco["livro_ausente"] is True
    assert _passo(laco, "estudios")["estado"] == "nao-consigo-olhar"
    assert _passo(laco, "estudios")["valor"] is None


def test_a_escola_sem_resposta_nao_vira_escola_vazia():
    laco = talentos.montar([], None, HOJE)

    assert _passo(laco, "alunas")["estado"] == "nao-medi"
    assert _passo(laco, "alunas")["valor"] is None


def test_a_etapa_sem_fonte_diz_o_motivo_escrito_no_cartao():
    laco = talentos.montar([], 133, HOJE)

    resultados = _passo(laco, "resultados")
    assert resultados["estado"] == "sem-fonte"
    assert resultados["cartao_lido"]["sem_fonte_porque"]


def test_zero_contado_e_zero_e_aparece_medido():
    laco = talentos.montar([_medicao("2026-09-20", f"{ESTUDIOS}=0")], 133, HOJE)

    assert _passo(laco, "estudios")["estado"] == "medido"
    assert _passo(laco, "estudios")["valor"] == 0


@respx.mock
def test_a_tela_diz_nunca_contado_em_vez_de_mostrar_zero():
    _a_escola_responde()

    html = _dentro().get(reverse("talentos")).content.decode()

    assert "nunca contado" in html
    assert "Ninguém contou esta etapa ainda" in html
    assert "Primeira vez aqui" in html, "o primeiro uso tem texto próprio"


def test_sem_cartao_a_etapa_nao_mostra_numero_nenhum(tmp_path):
    """A lei do plano (§2): número sem cartão não aparece em tela nenhuma."""
    laco = talentos.montar([], 133, HOJE, pasta=tmp_path)

    for passo in laco["passos"]:
        assert passo["estado"] == "sem-cartao"
        assert passo["valor"] is None
        assert passo["problemas"]


# ---------------------------------------------------------------------------
# Contagens digitadas ficam no banco e aparecem depois de recarregar
# ---------------------------------------------------------------------------


@respx.mock
def test_contagem_salva_e_consultada_em_outra_requisicao():
    _a_escola_responde()
    cliente = _dentro()

    resposta = cliente.post(reverse("talentos"), {"talentos": "4", "estudios": "0"})
    assert resposta.status_code == 302
    linhas = list(RegistroDoPlacar.objects.filter(arquivo__startswith="talentos-"))
    assert len(linhas) == 1
    assert linhas[0].dados["quando"] == HOJE.isoformat()
    assert linhas[0].dados["autoridade"] == DONO
    assert f"{TALENTOS}=4" in linhas[0].dados["foto"]
    assert f"{ESTUDIOS}=0" in linhas[0].dados["foto"]

    pagina = cliente.get(reverse("talentos"))
    assert pagina.status_code == 200
    assert _passo(pagina.context["laco"], "talentos")["valor"] == 4
    assert _passo(pagina.context["laco"], "estudios")["valor"] == 0

    cliente.post(reverse("talentos"), {"estudios": "2"})
    assert RegistroDoPlacar.objects.filter(arquivo__startswith="talentos-").count() == 2
    pagina = cliente.get(reverse("talentos"))
    assert _passo(pagina.context["laco"], "talentos")["valor"] == 4
    assert _passo(pagina.context["laco"], "estudios")["valor"] == 2


# ---------------------------------------------------------------------------
# 4 e 5. Campo vazio não é zero; entrada inválida é recusada em português
# ---------------------------------------------------------------------------


def test_campo_vazio_nao_e_zero():
    contagens, recusas = talentos.ler_as_contagens(
        {"talentos": "4", "estudios": "", "encaixes": "   "}
    )

    assert contagens == {TALENTOS: 4}
    assert recusas == []


def test_zero_digitado_entra_como_zero():
    contagens, recusas = talentos.ler_as_contagens({"estudios": "0"})

    assert contagens == {ESTUDIOS: 0}
    assert recusas == []


def test_texto_no_lugar_do_numero_e_recusado_e_nada_entra():
    contagens, recusas = talentos.ler_as_contagens({"estudios": "uns três"})

    assert contagens == {}
    assert len(recusas) == 1
    assert "uns três" in recusas[0] and "número inteiro" in recusas[0]


def test_contagem_negativa_e_recusada():
    contagens, recusas = talentos.ler_as_contagens({"encaixes": "-2"})

    assert contagens == {}
    assert "não pode ser negativo" in recusas[0]


def test_a_recusa_cita_a_etiqueta_da_tela_e_nunca_o_nome_do_cartao():
    """Ele nunca viu `estudios-parceiros`: ele leu uma frase em português.

    Uma recusa que cita o nome interno manda o leigo procurar na tela uma
    palavra que não está lá.
    """
    _, recusas = talentos.ler_as_contagens({"estudios": "dois", "encaixes": "-1"})

    inteiro = " ".join(recusas)
    assert "Estúdios que já aceitaram receber alunas" in inteiro
    assert "Trabalhos que alunas já começaram em estúdios" in inteiro
    for _campo, cartao, _rotulo in talentos.DIGITADAS:
        assert cartao not in inteiro, "nome de cartão não se mostra a leigo"


@respx.mock
def test_entrada_invalida_nao_grava_metade():
    _a_escola_responde()
    resposta = _dentro().post(
        reverse("talentos"), {"talentos": "4", "estudios": "dois"}
    )
    assert resposta.status_code == 200
    assert "Não gravei nada" in resposta.content.decode()
    assert RegistroDoPlacar.objects.filter(arquivo__startswith="talentos-").count() == 0


@respx.mock
def test_post_vazio_diz_que_nao_ha_o_que_salvar():
    _a_escola_responde()
    html = _dentro().post(reverse("talentos"), {}).content.decode()
    assert "Nada para salvar" in html
    assert RegistroDoPlacar.objects.filter(arquivo__startswith="talentos-").count() == 0


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )

    assert Client().get(reverse("talentos")).status_code != 200


@respx.mock
def test_o_placar_leva_ate_a_rede_de_talentos():
    _a_escola_responde()

    html = _dentro().get(reverse("placar")).content.decode()

    assert reverse("talentos") in html


# ---------------------------------------------------------------------------
# 7. O laço tem os seis passos do documento, e a última contagem vence
# ---------------------------------------------------------------------------


def test_a_contagem_mais_recente_vence_a_anterior():
    registros = [
        _medicao("2026-09-01", f"{ESTUDIOS}=1", "antigo"),
        _medicao("2026-09-18", f"{ESTUDIOS}=3", "novo"),
    ]

    laco = talentos.montar(registros, 133, HOJE)

    assert _passo(laco, "estudios")["valor"] == 3
    assert _passo(laco, "estudios")["contado_em"] == dt.date(2026, 9, 18)
    assert _passo(laco, "estudios")["dias"] == 3


def test_a_contagem_velha_e_dita_como_velha():
    laco = talentos.montar([_medicao("2026-07-01", f"{ESTUDIOS}=3")], 133, HOJE)

    assert _passo(laco, "estudios")["velha"] is True


def test_a_contagem_dentro_do_prazo_do_cartao_nao_e_velha():
    laco = talentos.montar([_medicao("2026-09-18", f"{ESTUDIOS}=3")], 133, HOJE)

    assert _passo(laco, "estudios")["velha"] is False


def test_uma_foto_sem_a_rede_nao_apaga_a_contagem_anterior():
    registros = [
        _medicao("2026-09-01", f"{ESTUDIOS}=3", "a-contagem"),
        _medicao("2026-09-20", "compras-no-ciclo=17", "a-foto-da-semana"),
    ]

    laco = talentos.montar(registros, 133, HOJE)

    assert _passo(laco, "estudios")["valor"] == 3


# ---------------------------------------------------------------------------
# 8. A tela fala português, mostra o número, e lê o livro uma vez só
# ---------------------------------------------------------------------------


@respx.mock
def test_a_data_da_contagem_sai_em_portugues(monkeypatch):
    """`LANGUAGE_CODE` não é declarado nesta célula, então o padrão é `en-us`.

    Sem o filtro `date`, o mantenedor, que só lê português, vê
    "Sept. 18, 2026". A irmã `placar.html` já usa `d/m/Y`, e `coortes.py`
    escreveu a lição.
    """
    _a_escola_responde()
    monkeypatch.setattr(
        direcao,
        "ler_registros",
        lambda pasta=None: [_medicao("2026-09-18", f"{ESTUDIOS}=3")],
    )

    html = _dentro().get(reverse("talentos")).content.decode()

    assert "18/09/2026" in html
    assert "Sept" not in html and "2026-09-18" not in html


@respx.mock
def test_a_tela_le_o_livro_uma_vez_por_requisicao(monkeypatch):
    """Duas varreduras de `apps/core/registros/` custam o dobro e podem discordar.

    O placar já paga a leitura (`placar.py`) e a devolve no contexto; ler de
    novo aqui seria um `read_text` por arquivo, mais de mil deles, para chegar
    à mesma lista. É a mesma regra que o placar escreve para as portas de rede.
    """
    _a_escola_responde()
    verdadeiro = direcao.ler_registros
    quantas = []

    def contando(pasta=None):
        quantas.append(1)
        return verdadeiro(pasta)

    monkeypatch.setattr(direcao, "ler_registros", contando)

    assert _dentro().get(reverse("talentos")).status_code == 200
    assert sum(quantas) == 1, f"o livro foi lido {sum(quantas)} vezes"


def test_o_placar_devolve_o_livro_que_ele_ja_leu():
    """A porta pela qual a tela reaproveita a leitura. Se ela sumir, a tela
    quebra alto (`KeyError`) em vez de dizer baixinho que o livro não chegou.
    """
    assert "registros" in placar.montar_o_placar(HOJE)


# ---------------------------------------------------------------------------
# 9. O passo medido pelo placar mostra o número, e nunca manda procurar noutra tela
# ---------------------------------------------------------------------------


def _cartao(pasta, nome: str, **campos) -> None:
    import json

    ficha = {
        "nome": nome,
        "tipo": "resultado",
        "andar": 1,
        "pergunta": f"Quanto é {nome}?",
        "definicao": "um cartão de mentira, só para o guarda",
        "formula": "inventada",
        "autoridade": "mantenedor",
        "dono": "mantenedor",
        "frequencia": "quando muda",
        "direcao": "subir",
        "unidade": "coisas",
        "par": "alunos-na-plataforma",
        "acao": "nada",
        "frescor_maximo": 30,
        "limiar_ambar": None,
        "limiar_vermelho": None,
        "versao": 1,
        "desde": "2026-09-07",
        "_por_que": "guarda",
        **campos,
    }
    (pasta / f"{nome}.json").write_text(json.dumps(ficha), encoding="utf-8")


def _pasta_do_laco(tmp_path, **do_resultado):
    for chave in (
        "alunos-na-plataforma",
        "alunos-selecionados-para-a-rede",
        "estudios-parceiros",
        "encaixes-com-estudio",
        "margem-mensal",
    ):
        _cartao(tmp_path, chave, fonte=None, sem_fonte_porque="ainda não")
    _cartao(tmp_path, "alunos-com-resultado-profissional", **do_resultado)
    return tmp_path


def test_o_passo_do_cartao_mostra_o_numero_que_o_placar_mediu(tmp_path):
    """O degrau 17 prometeu o número AO LADO da etapa, e não um "veja no placar".

    Antes, o único ramo possível era "sem dados": os dois cartões de origem
    `cartao` têm `fonte` nula, e o ramo que diria "está no placar" nunca era
    alcançado e nunca mostrava número nenhum.
    """
    pasta = _pasta_do_laco(tmp_path, fonte="a célula alunos, ao vivo")

    laco = talentos.montar(
        [], 133, HOJE, {"alunos-com-resultado-profissional": 9}, pasta=pasta
    )

    assert _passo(laco, "resultados")["estado"] == "medido"
    assert _passo(laco, "resultados")["valor"] == 9


def test_cartao_com_fonte_sem_numero_nao_vira_sem_dados(tmp_path):
    """Três fatos, três frases (`armadilhas/271`).

    "O cartão não tem fonte" e "tem fonte e o placar não trouxe o número" são
    coisas diferentes, e a segunda não pode cair na primeira: `sem_fonte_porque`
    só é obrigatório quando a fonte é nula, e a tela sairia com a frase em
    branco.
    """
    pasta = _pasta_do_laco(tmp_path, fonte="a célula alunos, ao vivo")

    laco = talentos.montar([], 133, HOJE, {}, pasta=pasta)

    assert _passo(laco, "resultados")["estado"] == "sem-numero-agora"
    assert _passo(laco, "resultados")["valor"] is None


def test_cartao_sem_fonte_continua_dizendo_o_porque_escrito_nele(tmp_path):
    pasta = _pasta_do_laco(tmp_path, fonte=None, sem_fonte_porque="sem portfólio ainda")

    laco = talentos.montar([], 133, HOJE, {}, pasta=pasta)

    assert _passo(laco, "resultados")["estado"] == "sem-fonte"
    assert _passo(laco, "resultados")["cartao_lido"]["sem_fonte_porque"]


# ---------------------------------------------------------------------------
# 10. O caminho se lê na ordem, e a etiqueta que ele lê é a que a recusa cita
# ---------------------------------------------------------------------------


@respx.mock
def test_o_caminho_sai_em_coluna_numerada_e_nunca_em_grade():
    """Numa grade de três colunas o passo 4 cai embaixo do passo 1.

    A única coisa que estas seis peças ensinam é a ORDEM, e numa grade a ordem
    vira posição na tela (o comentário do bloco `.etapas` em `base.html`).
    """
    _a_escola_responde()

    html = _dentro().get(reverse("talentos")).content.decode()
    caminho = html.split("O caminho, etapa por etapa")[1].split("E daqui volta")[0]

    assert 'class="etapas"' in caminho
    assert caminho.count('class="etapa"') == 6
    assert 'class="notas"' not in caminho, "a grade de 3 colunas embaralha a ordem"
    for degrau in range(1, 7):
        assert f'class="etapa-degrau">{degrau}<' in caminho


@respx.mock
def test_as_tres_etiquetas_do_formulario_saem_de_digitadas():
    """Etiqueta na tela e nome citado na recusa são a MESMA frase, por construção.

    Duas listas escritas à mão divergem em silêncio, e a recusa passa a mandar
    procurar uma palavra que não está no formulário.
    """
    _a_escola_responde()

    html = _dentro().get(reverse("talentos")).content.decode()

    for campo, _cartao, rotulo in talentos.DIGITADAS:
        assert f"{rotulo}, no total" in html
        assert f'name="{campo}"' in html
