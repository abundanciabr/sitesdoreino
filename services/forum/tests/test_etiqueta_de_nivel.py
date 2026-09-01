"""A etiqueta "Nv 7 · Modelador" ao lado de quem escreve no fórum.

Cada guarda deste arquivo corresponde a uma forma diferente de isto dar errado,
e a mais cara delas não é a etiqueta sair torta: é a **conversa deixar de
abrir** porque um enfeite não pôde ser desenhado.

1. **O fórum cair porque a gamificação caiu** (ou porque o par de tokens ainda
   não foi provisionado, que é o estado real de hoje). A conversa tem de abrir
   igual, com 200, e é este o guarda mais importante do arquivo.
2. **A chamada em LOTE ser desfeita.** Uma página com N autores faz UMA
   consulta. Este desenho é desfeito de boa-fé pelo próximo agente que achar
   mais legível perguntar dentro do laço, e sem um guarda nada fica vermelho:
   a tela continua idêntica, só que com vinte saltos de rede em vez de um.
3. **Um rótulo ser CHUTADO a partir do slug.** `titulo_slug` perde acento e
   junta as palavras com hífen; desfazê-lo dá "Aprendiz De Atelie". Slug que
   não está no mapa de `apps/core/etiquetas.py` desenha só "Nv 7".
4. **A escola ganhar nível.** Fala publicada pela instituição não é de uma
   pessoa e nunca recebe etiqueta.
5. **O estilo não chegar ao navegador.** O fórum serve o CSS por rota própria
   (`armadilhas/083`), então classe nova no HTML sem regra na folha é um selo
   sem forma, e nada fica vermelho.

## Por que a rede é dublada no TRANSPORTE, com `respx`

O dublê é `respx`, que troca o transporte do `httpx` — nunca um `monkeypatch`
da função `etiquetas_de`. Substituir a própria função a ser provada faz o teste
concordar consigo mesmo: ele passaria inclusive com a URL errada, com o Bearer
ausente e com o corpo lido do campo errado, que são justamente os três defeitos
que esta suíte existe para pegar.

O `sem_rede` do `conftest.py` é `autouse` e troca `httpx.Client.get` por uma
recusa, o que deixaria o `respx` embaixo dele inalcançável. A fixture `porta`
devolve o método verdadeiro **só para os testes deste arquivo** antes de armar o
dublê — e o corte continua valendo para o resto da suíte. Nenhuma chamada além
das registradas passa: `respx` levanta `AllMockedAssertionError` em rota não
registrada (`armadilhas/054`), o que é exatamente o que se quer aqui, porque
uma consulta inesperada é um defeito.
"""

import httpx
import pytest
import respx
from django.urls import reverse

from apps.core import etiquetas as motor
from apps.forum.models import Area, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db

# O endereço sai do `servers:` do contrato congelado da gamificação
# (`contracts/gamificacao.openapi.yaml`), e a URL INTEIRA é conferida no dublê,
# não só o hostname: o segmento errado no meio já foi um bug real desta célula
# com a `alunos` — 404 silencioso que virou fail-closed para todo mundo, com o
# deploy verde (`armadilhas/111`, e o comentário em `apps/core/clients.py`).
GAMIFICACAO = "http://gamificacao:8000/api/gamificacao"
PERFIS = f"{GAMIFICACAO}/perfis"
TOKEN = "token-do-par-forum-gamificacao"

# Capturado no IMPORT do módulo, ou seja, antes de o `sem_rede` do conftest
# rodar: é o `get` de verdade, o que enxerga o transporte que o `respx` troca.
_GET_DE_VERDADE = httpx.Client.get


@pytest.fixture(autouse=True)
def cache_limpo():
    """O cache de módulo não pode vazar entre testes (`armadilhas/026`).

    Sem esta limpeza, uma etiqueta que um teste ensinou faria o guarda do teste
    seguinte passar por herança e não por medição — e o guarda do "UMA chamada"
    passaria com ZERO chamadas, o que não prova nada.
    """
    motor.limpar_cache()
    yield
    motor.limpar_cache()


@pytest.fixture
def porta(monkeypatch):
    """A porta da gamificação, dublada no transporte, com o par provisionado."""
    monkeypatch.setenv("GAMIFICACAO_API_URL", GAMIFICACAO)
    monkeypatch.setenv("GAMIFICACAO_API_TOKEN", TOKEN)
    monkeypatch.setattr(httpx.Client, "get", _GET_DE_VERDADE)
    with respx.mock(assert_all_called=False) as dublador:
        yield dublador


@pytest.fixture
def sem_par(monkeypatch):
    """O estado real enquanto o passo do mantenedor não roda: nada no env."""
    monkeypatch.delenv("GAMIFICACAO_API_URL", raising=False)
    monkeypatch.delenv("GAMIFICACAO_API_TOKEN", raising=False)


@pytest.fixture
def area_publica():
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas gerais",
        descricao="Pergunte sem medo.",
        visibilidade=Area.Visibilidade.PUBLICA,
    )


@pytest.fixture
def ana():
    return Pessoa.objects.create(
        id_da_plataforma="pessoa-ana", email="ana@exemplo.com", nome_exibido="Ana"
    )


@pytest.fixture
def conversa(area_publica, ana):
    topico = Topico.objects.create(
        area=area_publica, autor=ana, titulo="Como texturizar?"
    )
    Mensagem.objects.create(topico=topico, autor=ana, texto="A dúvida.")
    return topico


def _abrir(client, topico) -> str:
    resposta = client.get(reverse("topico", args=[topico.pk]))
    # 200 em TODOS os casos deste arquivo, inclusive nos de falha: a etiqueta é
    # enfeite, e enfeite não decide se a conversa abre.
    assert resposta.status_code == 200
    return resposta.content.decode()


# ---------------------------------------------------------------------------
# 1. A conversa abre, tenha etiqueta ou não
# ---------------------------------------------------------------------------


def test_gamificacao_fora_do_ar_nao_derruba_a_conversa(client, porta, conversa):
    """O guarda mais importante do arquivo."""
    porta.get(PERFIS).mock(side_effect=httpx.ConnectError("sem rede"))
    corpo = _abrir(client, conversa)
    assert "A dúvida." in corpo
    assert "Nv " not in corpo


def test_par_de_tokens_ausente_nao_custa_nem_uma_tentativa_de_rede(
    client, sem_par, conversa
):
    """Sem env, a conversa abre e a rede nem é tocada.

    O `sem_rede` do conftest continua valendo neste teste: se algum caminho
    tentasse perguntar, a chamada levantaria e o teste ficaria vermelho. É a
    prova de que a variável ausente é lida no PONTO DE USO e desiste ANTES da
    rede (`armadilhas/097`), em vez de virar 500 em toda página do fórum.
    """
    corpo = _abrir(client, conversa)
    assert "A dúvida." in corpo
    assert "Nv " not in corpo


def test_a_gamificacao_respondendo_erro_nao_derruba_a_conversa(client, porta, conversa):
    porta.get(PERFIS).mock(return_value=httpx.Response(503))
    assert "Nv " not in _abrir(client, conversa)


def test_corpo_fora_do_contrato_nao_derruba_a_conversa(client, porta, conversa):
    """`200` com corpo que não é JSON: proxy interposto, resposta truncada.

    `json.JSONDecodeError` é `ValueError` e NÃO é `httpx.RequestError` — fora
    do `try` certo ela subiria crua e viraria 500 na conversa inteira. É a
    família do *2xx não é sucesso* (`RETROSPECTIVA-FASE-D` §4).
    """
    porta.get(PERFIS).mock(
        return_value=httpx.Response(200, text="<html>erro do proxy</html>")
    )
    assert "Nv " not in _abrir(client, conversa)


@pytest.mark.parametrize(
    "linha",
    [
        # Campo com outro nome: a porta mudou e ninguém avisou.
        {"level": 7},
        # NÍVEL NULO com slug bom. Sem a conferência do número, isto desenharia
        # "Nv None · Modelador" na cara do aluno — e o slug válido esconde o
        # defeito de quem só confere o título.
        {"nivel": None, "titulo_slug": "modelador"},
        # `isinstance(True, int)` é VERDADEIRO em Python: sem a linha que
        # exclui `bool`, isto vira "Nv True · Modelador".
        {"nivel": True, "titulo_slug": "modelador"},
        # Número que não é degrau nenhum.
        {"nivel": 0, "titulo_slug": "modelador"},
        # Título que não é texto.
        {"nivel": 3, "titulo_slug": 42},
        # A linha inteira fora de forma.
        "modelador",
    ],
)
def test_linha_com_o_campo_errado_nao_vira_etiqueta_torta(
    client, porta, conversa, linha
):
    """Corpo que é JSON mas não é o contrato.

    Confiar sem conferir é como um `null` do outro lado vira `TypeError` no
    meio do template — e ali já não há como falhar aberto, porque a página está
    sendo renderizada. Cada caso desta lista é um campo diferente da conferência
    de `_etiqueta_do_corpo`: com um só, os outros passariam por herança.
    """
    porta.get(PERFIS).mock(return_value=httpx.Response(200, json={"pessoa-ana": linha}))
    assert "Nv " not in _abrir(client, conversa)


# ---------------------------------------------------------------------------
# 2. Com a porta respondendo
# ---------------------------------------------------------------------------


def test_a_etiqueta_aparece_com_o_rotulo_em_portugues(client, porta, conversa):
    """O slug vira frase pelo mapa do fórum, com acento e preposição minúscula.

    `artesao-de-atelie` sai como "Artesão de Ateliê". Derivado do slug daria
    "Artesao De Atelie" — que é exatamente o motivo de o mapa existir.
    """
    porta.get(PERFIS).mock(
        return_value=httpx.Response(
            200, json={"pessoa-ana": {"nivel": 8, "titulo_slug": "artesao-de-atelie"}}
        )
    )
    corpo = _abrir(client, conversa)
    assert "Nv 8" in corpo
    assert "Artesão de Ateliê" in corpo


def test_slug_fora_do_mapa_desenha_so_o_nivel(client, porta, conversa):
    """O dia em que o mantenedor renomear um degrau na `gamificacao`.

    A etiqueta sai como "Nv 4", que é verdade, e NUNCA um rótulo chutado a
    partir do slug. O conserto é acrescentar a linha em `ROTULO_POR_SLUG`, no
    mesmo PR que mudou o título lá.
    """
    porta.get(PERFIS).mock(
        return_value=httpx.Response(
            200, json={"pessoa-ana": {"nivel": 4, "titulo_slug": "grao-mestre-supremo"}}
        )
    )
    corpo = _abrir(client, conversa)
    assert "Nv 4" in corpo
    assert "Grao" not in corpo
    assert "Supremo" not in corpo


def test_id_omitido_do_mapa_nao_desenha_etiqueta(client, porta, area_publica, ana):
    """Id desconhecido é OMITIDO do mapa, por contrato — nunca erro, nunca vazio.

    Este é o caso COMUM no começo: quase ninguém pontuou ainda. A linha de quem
    não tem etiqueta fica exatamente como era antes desta entrega.
    """
    bruno = Pessoa.objects.create(
        id_da_plataforma="pessoa-bruno", email="bruno@exemplo.com", nome_exibido="Bruno"
    )
    topico = Topico.objects.create(area=area_publica, autor=ana, titulo="Dupla")
    Mensagem.objects.create(topico=topico, autor=ana, texto="fala da Ana")
    Mensagem.objects.create(topico=topico, autor=bruno, texto="fala do Bruno")

    porta.get(PERFIS).mock(
        return_value=httpx.Response(
            200, json={"pessoa-ana": {"nivel": 3, "titulo_slug": "modelador"}}
        )
    )
    corpo = _abrir(client, topico)
    assert "Bruno" in corpo
    assert corpo.count("Nv ") == 1
    assert "Nv 3" in corpo


# ---------------------------------------------------------------------------
# 3. O LOTE — uma chamada por página, e este guarda protege o desenho
# ---------------------------------------------------------------------------


def test_uma_pagina_com_varios_autores_faz_UMA_chamada_de_rede(
    client, porta, area_publica, ana
):
    """Três autores, três mensagens, UMA consulta com os três ids juntos.

    Sem este guarda o desenho é desfeito de boa-fé: perguntar dentro do laço do
    template é mais legível e deixa a tela idêntica. O custo só aparece em
    produção, e cresce com o tamanho da conversa.
    """
    bruno = Pessoa.objects.create(
        id_da_plataforma="pessoa-bruno", email="bruno@exemplo.com", nome_exibido="Bruno"
    )
    clara = Pessoa.objects.create(
        id_da_plataforma="pessoa-clara", email="clara@exemplo.com", nome_exibido="Clara"
    )
    topico = Topico.objects.create(area=area_publica, autor=ana, titulo="Trio")
    for quem in (ana, bruno, clara, ana, bruno):
        Mensagem.objects.create(topico=topico, autor=quem, texto=f"fala {quem.pk}")

    rota = porta.get(PERFIS).mock(
        return_value=httpx.Response(
            200,
            json={
                "pessoa-ana": {"nivel": 3, "titulo_slug": "modelador"},
                "pessoa-bruno": {"nivel": 1, "titulo_slug": "aprendiz"},
                "pessoa-clara": {"nivel": 9, "titulo_slug": "mestre"},
            },
        )
    )
    corpo = _abrir(client, topico)

    assert rota.call_count == 1, "uma página, uma consulta — o lote foi desfeito"
    pedidos = rota.calls[0].request.url.params["ids"].split(",")
    assert sorted(pedidos) == ["pessoa-ana", "pessoa-bruno", "pessoa-clara"]
    # Cinco mensagens, três autores: o id repetido não vira id repetido no lote.
    assert len(pedidos) == 3
    assert "Modelador" in corpo and "Aprendiz" in corpo and "Mestre" in corpo


def test_o_bearer_do_par_viaja_na_chamada(client, porta, conversa):
    """O Bearer prova QUEM CHAMA, e sem ele a porta responde 401.

    Vale a pena travar: é o tipo de coisa que passa despercebida porque o dublê
    responde 200 de qualquer jeito, e só a produção reclama.
    """
    rota = porta.get(PERFIS).mock(return_value=httpx.Response(200, json={}))
    _abrir(client, conversa)
    assert rota.calls[0].request.headers["Authorization"] == f"Bearer {TOKEN}"


def test_a_segunda_abertura_da_mesma_conversa_nao_repete_a_consulta(
    client, porta, conversa
):
    """O cache por TTL curto: nível muda devagar, página é aberta o tempo todo."""
    rota = porta.get(PERFIS).mock(
        return_value=httpx.Response(
            200, json={"pessoa-ana": {"nivel": 3, "titulo_slug": "modelador"}}
        )
    )
    _abrir(client, conversa)
    _abrir(client, conversa)
    assert rota.call_count == 1


def test_aluno_sem_etiqueta_tambem_e_lembrado(client, porta, conversa):
    """A ausência é guardada, e é o que faz o cache valer a pena.

    Quem nunca pontuou é a maioria no começo. Se só o positivo fosse lembrado,
    justamente esse aluno custaria uma consulta de rede em toda página aberta.
    """
    rota = porta.get(PERFIS).mock(return_value=httpx.Response(200, json={}))
    _abrir(client, conversa)
    _abrir(client, conversa)
    assert rota.call_count == 1


# ---------------------------------------------------------------------------
# 3b. O mapa de rótulos não pode envelhecer errado em silêncio
# ---------------------------------------------------------------------------


def test_toda_chave_do_mapa_e_mesmo_o_slug_do_seu_rotulo():
    """Cada chave tem de ser `slugify` do rótulo que ela aponta.

    É a invariante do mapa: a chave nasce lá na `gamificacao` como
    `slugify(titulo)`, então uma chave que não seja o slug do próprio rótulo
    **nunca casa com nada**. O efeito de um erro de digitação é SILENCIOSO —
    a etiqueta cai no fallback e mostra só "Nv 7", que é exatamente o modo de
    falha que o resto deste arquivo existe para evitar. Nada fica vermelho,
    ninguém vê exceção, e o título simplesmente não aparece mais.

    Conferido de fora, com o `slugify` de verdade: os dez títulos da lista
    `NIVEIS` de `semear_economia.py` passam por aqui, um a um, e batem. A lista
    da outra célula NÃO é importada (Lei 3), então este guarda prova a forma do
    mapa; quem prova o conteúdo é o comentário que aponta a fonte.
    """
    from django.utils.text import slugify

    for chave, rotulo in motor.ROTULO_POR_SLUG.items():
        assert slugify(rotulo) == chave, (
            f"a chave {chave!r} não é o slug de {rotulo!r} (que dá "
            f"{slugify(rotulo)!r}) — ela nunca vai casar, e a etiqueta vai "
            f"cair no fallback em silêncio"
        )


# ---------------------------------------------------------------------------
# 4. A escola não tem nível
# ---------------------------------------------------------------------------


def test_fala_publicada_pela_escola_nao_recebe_etiqueta(
    client, porta, area_publica, ana
):
    """A Meshcraft Academy não é uma aluna, e estampar um nível nela seria
    fingir que é. Vale para o tópico semeado e para a resposta oficial."""
    topico = Topico.objects.create(
        area=area_publica, publicado_pela_escola=True, titulo="Aviso"
    )
    Mensagem.objects.create(
        topico=topico, publicado_pela_escola=True, texto="A escola avisa."
    )
    Mensagem.objects.create(topico=topico, autor=ana, texto="fala da Ana")

    porta.get(PERFIS).mock(
        return_value=httpx.Response(
            200, json={"pessoa-ana": {"nivel": 3, "titulo_slug": "modelador"}}
        )
    )
    corpo = _abrir(client, topico)
    assert "Meshcraft Academy" in corpo
    # Uma etiqueta só na página inteira, e ela é da Ana.
    assert corpo.count("Nv ") == 1
    assert "Nv 3" in corpo


def test_a_bandeira_da_escola_sozinha_ja_tira_a_etiqueta(porta, ana):
    """A regra medida DIRETO, sem passar pelo banco, e o motivo é uma medição.

    O teste de cima passa mesmo se `publicado_pela_escola` for ignorado, porque
    hoje o banco garante que fala da escola tem autor NULO
    (`_fala_de_pessoa_ou_da_escola`, `apps/forum/models.py`) — ou seja, a
    condição do autor sozinha já esconde a etiqueta, e a regra de produto passa
    por herança. Medido em 01/09/2026: apagar a bandeira de `decorar` deixava a
    suíte inteira verde.

    Aqui a mensagem NÃO é salva, de propósito: a restrição do banco recusaria
    esta combinação, e é justamente ela que precisa ser provada sem depender de
    uma restrição continuar existindo. `decorar` só lê `autor_id` e
    `publicado_pela_escola`, então o objeto em memória basta.
    """
    porta.get(PERFIS).mock(
        return_value=httpx.Response(
            200, json={"pessoa-ana": {"nivel": 3, "titulo_slug": "modelador"}}
        )
    )
    da_escola = Mensagem(autor=ana, publicado_pela_escola=True, texto="oficial")
    de_pessoa = Mensagem(autor=ana, publicado_pela_escola=False, texto="normal")

    motor.decorar([da_escola, de_pessoa])

    assert da_escola.etiqueta is None
    assert de_pessoa.etiqueta == motor.Etiqueta(nivel=3, titulo="Modelador")


def test_conversa_so_da_escola_nao_pergunta_nada(client, porta, area_publica):
    """Nem cache, nem rede: página sem pessoa nenhuma não tem o que perguntar."""
    topico = Topico.objects.create(
        area=area_publica, publicado_pela_escola=True, titulo="Aviso"
    )
    Mensagem.objects.create(
        topico=topico, publicado_pela_escola=True, texto="A escola avisa."
    )
    rota = porta.get(PERFIS).mock(return_value=httpx.Response(200, json={}))
    _abrir(client, topico)
    assert rota.call_count == 0


# ---------------------------------------------------------------------------
# 5. O estilo chega ao navegador
# ---------------------------------------------------------------------------


def test_o_estilo_da_etiqueta_chega_ao_navegador(client):
    """Classe nova no HTML sem regra na folha é um selo sem forma, e nada fica
    vermelho. O fórum serve o CSS por rota própria (`armadilhas/083`)."""
    resposta = client.get(reverse("estatico", args=["forum.css"]))
    folha = (
        b"".join(resposta.streaming_content).decode("utf-8")
        if resposta.streaming
        else resposta.content.decode("utf-8")
    )
    assert ".mensagem .nivel" in folha
