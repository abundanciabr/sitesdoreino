"""A área do lançamento perpétuo, `/admin/perpetuo/` (02/09/2026).

O que estes guardas protegem:

1. **Nenhuma porta escrita na máquina aponta para o vazio.** As seis peças
   nomeiam endereços do site, e quem descreve esses endereços é
   `painel/mapa-do-site.json`. Um endereço que mudar de forma lá e continuar
   escrito aqui vira link para 404, e o mantenedor conclui que o site quebrou.
   Este é o guarda principal do arquivo, e o motivo de ele existir.
2. **A tela não guarda cópia de nome nem de explicação.** O que ela mostra de
   cada porta sai do mapa. Uma segunda cópia aqui dentro seria a duplicação que
   o `CLAUDE.md` proíbe, e envelheceria em silêncio.
3. **Molde não vira link** (`/quiz/quiz/<slug:slug>/` não é um lugar).
4. **Mapa ausente se DECLARA**, e a página abre mesmo assim: as seis peças são
   conceito, e continuam verdadeiras sem o arquivo. O que não pode é a tela
   ficar calada sobre os links que faltam.
5. **A porta continua sendo a porta**: sem crachá, esta página não abre.
6. **A visão geral leva até aqui.** Botão que ninguém encontra é
   funcionalidade que não existe, e foi assim que o editor de documentos passou
   dois dias invisível.
"""

import json
import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import perpetuo

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


def _mapa() -> dict:
    """O `painel/mapa-do-site.json` de verdade, indexado pelo endereço."""
    mapa = perpetuo._mapa_por_endereco()
    assert mapa is not None, (
        "o mapa do site não foi encontrado — em produção ele vem em "
        "`painel_embutido/`, num checkout em `painel/`. Se este assert falhou, "
        "a tela do perpétuo abriria sem link nenhum."
    )
    return mapa


def test_toda_porta_existe_no_mapa_do_site():
    """O guarda principal: endereço escrito numa peça que o mapa não conhece.

    Sem ele, o dia em que alguém renomear uma rota (e atualizar o mapa, porque
    lá a muralha obriga) esta tela continuaria oferecendo o endereço velho, e
    ninguém saberia até o mantenedor clicar e cair num 404.

    A mensagem de falha traz o endereço EXATO e o que fazer, porque quem vai
    lê-la é o robô que quebrou isto sem saber que esta tela existia.
    """
    mapa = _mapa()
    orfas = [
        (etapa["chave"], endereco)
        for etapa in perpetuo.ETAPAS
        for endereco in etapa["portas"]
        if endereco not in mapa
    ]
    assert not orfas, (
        f"endereços que a máquina do perpétuo cita e o mapa do site não tem: "
        f"{orfas}. Conserte a lista `ETAPAS` em apps/core/perpetuo.py com o "
        f"endereço novo (o certo está em painel/mapa-do-site.json), ou tire a "
        f"porta da peça se a tela deixou de existir."
    )


def test_nenhuma_peca_fica_sem_porta():
    """Peça sem porta nenhuma é um cartão que não ensina nada.

    Não é obrigação eterna do desenho: é a afirmação de que, HOJE, cada uma das
    seis etapas tem ao menos um lugar do site que a serve. No dia em que uma
    peça ficar vazia de verdade, o texto dela precisa dizer isso em voz alta,
    e não sumir por dentro.
    """
    vazias = [e["chave"] for e in perpetuo.ETAPAS if not e["portas"]]
    assert not vazias, f"peças sem porta nenhuma: {vazias}"


def test_o_codigo_nao_guarda_copia_do_nome_das_telas():
    """A lei anti-duplicação, medida: o nome de uma porta não mora aqui.

    Se um título do mapa aparecer escrito dentro de `perpetuo.py`, existem duas
    verdades sobre o nome daquela tela — e no dia em que divergirem, ninguém
    sabe qual está certa.
    """
    fonte = Path(perpetuo.__file__).read_text(encoding="utf-8")
    copiados = [
        entrada["titulo"]
        for entrada in _mapa().values()
        if entrada.get("titulo") and entrada["titulo"] in fonte
    ]
    assert not copiados, f"títulos de tela copiados para dentro do código: {copiados}"


@respx.mock
def test_a_pagina_abre_e_mostra_as_seis_pecas():
    resposta = _dentro().get(reverse("perpetuo"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    for etapa in perpetuo.ETAPAS:
        assert etapa["nome"] in html, f"a peça {etapa['chave']} sumiu da tela"
    assert len(perpetuo.ETAPAS) == 6


@respx.mock
def test_o_nome_de_cada_porta_vem_do_mapa_e_chega_a_tela():
    """O que a tela mostra de uma porta é o que o mapa diz dela, hoje."""
    html = _dentro().get(reverse("perpetuo")).content.decode()
    mapa = _mapa()
    sumidos = [
        mapa[endereco]["titulo"]
        for etapa in perpetuo.ETAPAS
        for endereco in etapa["portas"]
        if endereco in mapa and mapa[endereco]["titulo"] not in html
    ]
    assert not sumidos, f"portas que sumiram no caminho: {sumidos}"


@respx.mock
def test_molde_nao_vira_link():
    """`/quiz/quiz/<slug:slug>/` não é um lugar: é a forma de todos os quizzes.

    Oferecê-lo como link manda o mantenedor para um 404, e ele conclui que o
    site quebrou. A regra de quando um endereço vira link é a do mapa do site,
    reusada e não copiada.
    """
    html = _dentro().get(reverse("perpetuo")).content.decode()
    assert 'href="/quiz/quiz/' not in html
    assert "/quiz/quiz/" in html, "mas o endereço continua à vista, como texto"


@respx.mock
def test_endereco_fora_do_mapa_grita_em_vez_de_sumir(monkeypatch):
    """Sumir em silêncio é a pior forma de perder um fato.

    Aqui a peça cita um endereço que o mapa não conhece: a linha precisa
    aparecer, com o endereço legível, e não desaparecer da lista.
    """
    inventado = "/isto-nao-existe-em-lugar-nenhum"
    monkeypatch.setattr(
        perpetuo,
        "ETAPAS",
        (
            {
                "chave": "teste",
                "nome": "Peça de teste",
                "pergunta": "?",
                "resumo": "...",
                "portas": (inventado,),
            },
        ),
    )
    html = _dentro().get(reverse("perpetuo")).content.decode()
    assert inventado in html
    assert "fora do mapa do site" in html


@respx.mock
def test_sem_o_mapa_a_pagina_abre_e_diz_que_faltou(monkeypatch):
    """Diferente do `/admin/mapa/`, que devolve 500: lá o arquivo É a página.

    Aqui as seis peças continuam verdadeiras sem ele. O que não pode é a tela
    ficar calada: um cartão sem links, sem explicação, seria lido como "esta
    peça não existe".
    """
    monkeypatch.setattr(perpetuo, "arquivo_do_mapa", lambda: None)
    resposta = _dentro().get(reverse("perpetuo"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Não consegui ler o mapa do site" in html
    assert perpetuo.ETAPAS[0]["nome"] in html


@respx.mock
def test_arquivo_torto_nao_vira_tela_pela_metade(monkeypatch, tmp_path):
    torto = tmp_path / "mapa-do-site.json"
    torto.write_text('{"enderecos": ', encoding="utf-8")
    monkeypatch.setattr(perpetuo, "arquivo_do_mapa", lambda: torto)
    html = _dentro().get(reverse("perpetuo")).content.decode()
    assert "Não consegui ler o mapa do site" in html


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    assert Client().get(reverse("perpetuo")).status_code != 200


@respx.mock
def test_a_visao_geral_leva_ate_a_area():
    """Botão que ninguém encontra é funcionalidade que não existe."""
    html = _dentro().get(reverse("visao_geral")).content.decode()
    assert f'href="{reverse("perpetuo")}"' in html


def test_o_mapa_do_site_conhece_esta_tela():
    """A muralha do cartógrafo já exige isto no CI; aqui a suíte da célula
    reprova antes, com a mensagem que diz onde escrever.

    A pergunta é pela ROTA (`perpetuo/`, a string exata do `urls.py`), e NÃO
    por `reverse()`: nesta suíte não há `SCRIPT_NAME`, então `reverse` devolve
    `/perpetuo/` enquanto o endereço público é `/admin/perpetuo/`. Compor
    endereço de célula somando prefixo é a `armadilhas/197`, e a primeira
    versão deste teste caiu nela.
    """
    caminho = perpetuo.arquivo_do_mapa()
    assert caminho is not None
    entradas = json.loads(caminho.read_text(encoding="utf-8"))["enderecos"]
    assert any(
        e.get("celula") == "admin" and e.get("rota") == "perpetuo/" for e in entradas
    ), (
        "a rota nova precisa de uma entrada em painel/mapa-do-site.json — "
        "o formato está no `_doc` do próprio arquivo"
    )


def test_a_tela_nao_traz_estilo_na_marcacao():
    """O estilo mora em admin/base.html. Um `style=` aqui voltaria a espalhar
    desenho pela marcação, que é o que `test_estilo_nao_volta_para_a_marcacao`
    varre na célula inteira; esta é a mesma régua, apontada para esta tela."""
    caminho = Path(perpetuo.__file__).parent / "templates" / "admin" / "perpetuo.html"
    assert not re.search(r"\sstyle=", caminho.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# O VEREDITO DE CADA PEÇA (07/09/2026)
# ---------------------------------------------------------------------------
# 7. **"Não respondeu" nunca vira "zero".** É a espinha desta tela: fila vazia
#    é uma máquina saudável, e célula muda é uma tela que não sabe de nada. Os
#    dois pintados da mesma cor mandariam o mantenedor comemorar um silêncio.
# 8. **Peça sem fonte não ganha número.** Ela diz o que falta construir. Um
#    palpite numa tela de decisão é pior que a ausência do número.
# 9. **O estado vem ESCRITO.** Cor sozinha exclui quem não distingue verde de
#    vermelho, e a casa já decidiu isso na `.luz` das portas principais.


def test_sequencia_desligada_e_parada():
    """A peça que faz o perpétuo ser perpétuo, desligada, é o achado mais caro
    desta tela: uma sequência desligada não avisa ninguém de que está, e o
    silêncio se parece com "está tudo bem"."""
    veredito = perpetuo._aquecer({"jornadas": [{"slug": "a", "ativa": False}]})
    assert veredito["estado"] == perpetuo.PARADA
    assert "DESLIGADAS" in veredito["frase"]


def test_sequencia_ligada_e_girando():
    veredito = perpetuo._aquecer(
        {"jornadas": [{"slug": "a", "ativa": True}, {"slug": "b", "ativa": False}]}
    )
    assert veredito["estado"] == perpetuo.GIRANDO
    assert "1 de 2" in veredito["frase"]


def test_celula_muda_nunca_vira_zero():
    """O guarda principal deste bloco.

    `None` é "não consegui perguntar" e `[]` é "perguntei, e não há nada".
    Achatados no mesmo veredito, uma célula fora do ar apareceria como uma
    máquina vazia — e o mantenedor iria consertar o que não está quebrado.
    """
    for ler, mudo, vazio in (
        (perpetuo._aquecer, None, {"jornadas": []}),
        (perpetuo._decidir, None, []),
        (perpetuo._entregar, None, []),
    ):
        assert (
            ler(mudo)["estado"] == perpetuo.NAO_RESPONDEU
        ), f"{ler.__name__}: célula muda precisa dizer que não respondeu"
        assert (
            ler(vazio)["estado"] != perpetuo.NAO_RESPONDEU
        ), f"{ler.__name__}: lista vazia é uma resposta, e não um silêncio"


def test_fila_vazia_e_girando_e_espera_longa_e_parada():
    """O veredito olha a ESPERA, e não o tamanho da fila: dez pedidos de ontem
    é uma máquina movimentada, e um pedido de cinco dias é alguém desistindo."""
    assert perpetuo._decidir([])["estado"] == perpetuo.GIRANDO
    de_hoje = [{"esperando_ha_dias": 0}, {"esperando_ha_dias": 1}]
    assert perpetuo._decidir(de_hoje)["estado"] == perpetuo.GIRANDO
    parado = de_hoje + [
        {"esperando_ha_dias": perpetuo.DIAS_DE_ESPERA_QUE_VIRAM_GARGALO}
    ]
    veredito = perpetuo._decidir(parado)
    assert veredito["estado"] == perpetuo.PARADA
    assert "esperando por você" in veredito["frase"]


def test_a_peca_que_faz_o_perpetuo_oferece_o_interruptor_dela():
    """A peça "Aquecer" se descreve como "as mensagens saem sozinhas", e por
    quatro dias não ofereceu a porta onde essas mensagens se ligam e se
    desligam: o dono lia a promessa sem ter como agir sobre ela.

    O endereço é o da tela das sequências. Este guarda não o nomeia (nome de
    tela vem do mapa, nunca do código), só exige que a peça o cite.
    """
    aquecer = next(e for e in perpetuo.ETAPAS if e["chave"] == "aquecer")
    assert "/admin/escola/jornadas/" in aquecer["portas"], (
        "a peça que define o lançamento perpétuo precisa oferecer o "
        "interruptor das sequências de mensagens"
    )


def test_peca_sem_fonte_diz_o_motivo_e_nao_inventa_numero(monkeypatch):
    """Duas peças a casa ainda não sabe medir, e elas declaram isso.

    O molde é o `ETAPAS` de `restricao.py`: a ausência de um número é um fato,
    e fato se declara. O que não pode é a peça mostrar um veredito de leitura
    que ninguém leu.
    """
    _sem_rede(monkeypatch)
    sem_fonte = [e for e in perpetuo.ETAPAS if e.get("sem_fonte_porque")]
    assert sem_fonte, "alguma peça precisa declarar que a casa não a mede"
    for etapa in sem_fonte:
        assert etapa["chave"] not in perpetuo.vereditos(None), (
            f"a peça {etapa['chave']} não tem fonte: ela não pode receber "
            "veredito de leitura"
        )
    montadas = perpetuo.etapas_com_portas(_mapa(), perpetuo.vereditos(None))
    for etapa in montadas:
        if etapa.get("sem_fonte_porque"):
            assert etapa["veredito"]["estado"] == perpetuo.SEM_FONTE
            assert etapa["veredito"]["frase"] == etapa["sem_fonte_porque"]


def test_a_peca_de_medir_le_do_placar_em_vez_de_contar_sozinha():
    """Quantas passagens do funil têm fonte é um fato que já mora em
    `restricao.ETAPAS`, e é de lá que esta peça o lê.

    Uma contagem própria aqui divergiria da tela do placar no dia em que uma
    fonte nova nascesse, e o mantenedor leria a que abrisse primeiro sem saber
    que a outra discorda.
    """
    from apps.core.restricao import ETAPAS as PASSAGENS

    com_fonte = sum(1 for p in PASSAGENS if p.get("fonte"))
    frase = perpetuo._medir()["frase"]
    assert str(len(PASSAGENS)) in frase and str(com_fonte) in frase, (
        f"a frase precisa citar os números do placar ({com_fonte} de "
        f"{len(PASSAGENS)}), e disse: {frase}"
    )


def _sem_rede(monkeypatch, respostas=None):
    """As três células, respondidas sem sair da máquina.

    `None` em qualquer uma é o silêncio dela, que é o caso que mais importa
    provar: em teste, uma célula que "não respondeu" é o estado normal, e a
    página precisa abrir assim mesmo.
    """
    padrao = {"aquecer": None, "decidir": None, "entregar": None}
    monkeypatch.setattr(
        perpetuo, "_perguntar_a_todas", lambda site_id: {**padrao, **(respostas or {})}
    )
    monkeypatch.setattr(perpetuo, "site_de", lambda request: "site-de-teste")


@respx.mock
def test_o_estado_de_cada_peca_aparece_escrito_e_nao_so_colorido(monkeypatch):
    """Cor sozinha exclui quem não distingue verde de vermelho.

    A casa já decidiu isso na `.luz` das portas principais, e esta tela reusa
    aquela regra: a palavra do estado sai no HTML, e a cor é o reforço.
    """
    _sem_rede(
        monkeypatch,
        {
            "aquecer": {"jornadas": [{"slug": "a", "ativa": True}]},
            "decidir": [],
            "entregar": [{"pessoa_id": "p1"}],
        },
    )
    html = _dentro().get(reverse("perpetuo")).content.decode()
    # A palavra tem de estar DEPOIS do `>`, no texto que a pessoa lê. Procurá-la
    # no HTML inteiro seria um guarda que mente: `class="luz girando"` já contém
    # "girando", e o teste passaria com a tela mostrando só uma bolinha colorida.
    # Foi o que aconteceu na primeira versão deste guarda, e a sabotagem pegou.
    assert re.search(
        r'class="luz girando"[^>]*>\s*girando', html
    ), "o estado precisa estar ESCRITO no texto, e não só na classe da cor"
    assert re.search(
        r'class="luz sem-fonte"[^>]*>\s*a casa não mede', html
    ), "a peça sem fonte precisa dizer isso por extenso"


@respx.mock
def test_celula_fora_do_ar_nao_derruba_a_pagina(monkeypatch):
    """Uma tela de operação que não abre é inútil justamente no dia em que
    você precisa dela. Com as três células mudas, a página continua 200, as
    seis peças continuam lá, e cada uma diz que não deu para perguntar."""
    _sem_rede(monkeypatch)
    resposta = _dentro().get(reverse("perpetuo"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    for etapa in perpetuo.ETAPAS:
        assert etapa["nome"] in html
    assert "não consegui perguntar" in html


@respx.mock
def test_sem_saber_o_site_a_tela_abre_e_as_outras_pecas_continuam(monkeypatch):
    """As sequências são por site: sem saber de qual perguntar, aquela peça
    fica sem resposta. As outras não dependem do site, e continuam valendo."""
    monkeypatch.setattr(perpetuo, "site_de", lambda request: None)
    monkeypatch.setattr(
        perpetuo.MensageriaClient,
        "jornadas",
        lambda self, site_id: pytest.fail("sem site, não se pergunta às sequências"),
    )
    monkeypatch.setattr(perpetuo.AlunosClient, "fila", lambda self, status: [])
    monkeypatch.setattr(perpetuo.GamificacaoClient, "quadro", lambda self: [])
    resposta = _dentro().get(reverse("perpetuo"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "a fila de entrada está vazia" in html
