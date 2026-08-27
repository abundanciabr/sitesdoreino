# tests/test_avisos_le_a_notificacoes.py  # [RECEITA:R5 v1]
"""A tela `/avisos` — fail VISÍVEL, a regra OPOSTA do sino (Escolha 2 de
`docs/decisoes/DECISAO-fase-4-do-sininho.md`).

Esta página É a função dela: se a caixa central de avisos
(`contracts/notificacoes.openapi.yaml`) não responde, a tela precisa dizer
isso — nunca fingir "zero avisos". `tests/test_sino_le_a_notificacoes.py`
mede a ponta OPOSTA (o sino no trilho, fail ABERTA); os dois arquivos juntos
provam que o MESMO dado tem comportamento DELIBERADAMENTE diferente conforme
a tela que o mostra.

Quatro assuntos, cada um com seção própria:

1. **Fail visível** — um teste por modo de falha, e o teste que prova que a
   frase da falha NUNCA é a mesma da lista vazia de verdade (a distinção que
   a Escolha 2 exige, byte a byte).
2. **N+1** — o título de cada sugestão citada é buscado em LOTE, nunca um por
   aviso (o título não viaja na carta, `DECISAO-fase-2-do-sininho.md` §4).
3. **`vinculo` ausente** — uma carta de antes de 27/08/2026 (sem o campo) não
   pode quebrar a tela nem inventar um rótulo que ninguém mandou.
4. **`marcar_lido`/`marcar_tudo_lido`** — o payload que chega à notificacoes,
   com o `id` opaco certo, e a idempotência do lado de lá.
"""

import json

import httpx
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.avisos import limpar_cache_de_resumo
from apps.sugestoes.models import Aviso, Sugestao

pytestmark = pytest.mark.django_db

MENSAGEM_DE_FALHA = "Não consegui buscar seus avisos agora"
MENSAGEM_DE_VAZIO_DE_VERDADE = "Nenhum aviso ainda"


def _chamadas(rede, pedaco_do_caminho: str) -> list:
    return [c for c in rede.mock.calls if pedaco_do_caminho in str(c.request.url)]


# ---------------------------------------------------------------------------
# 1. Fail VISÍVEL — um teste por modo de falha
# ---------------------------------------------------------------------------
def test_a_lista_aparece_quando_a_notificacoes_responde(dentro, aviso):
    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert aviso.sugestao.titulo in corpo
    assert MENSAGEM_DE_FALHA not in corpo


def test_falha_e_diferente_de_vazio_de_verdade(dentro, outra_pessoa, aviso, rede):
    """[Escolha 2] O texto da falha NUNCA é o texto de "zero avisos de
    verdade" — são estados diferentes, nunca o mesmo visual.

    `outra_pessoa` não tem NENHUM aviso (o vazio de verdade, com a
    notificacoes respondendo normalmente); `dentro` tem um, mas a
    notificacoes está fora do ar para ele. As duas páginas precisam dizer
    coisas DIFERENTES uma da outra.
    """
    pagina_vazia_de_verdade = outra_pessoa.client.get(
        reverse("avisos")
    ).content.decode()

    rede.notificacoes_avisos.mock(side_effect=httpx.ConnectError("connection refused"))
    pagina_de_falha = dentro.client.get(reverse("avisos"))

    assert MENSAGEM_DE_VAZIO_DE_VERDADE in pagina_vazia_de_verdade
    assert MENSAGEM_DE_FALHA not in pagina_vazia_de_verdade

    assert MENSAGEM_DE_FALHA in pagina_de_falha.content.decode()
    assert MENSAGEM_DE_VAZIO_DE_VERDADE not in pagina_de_falha.content.decode()
    assert pagina_de_falha.status_code == 503


def test_falha_quando_a_rede_recusa_a_conexao(dentro, aviso, rede):
    rede.notificacoes_avisos.mock(side_effect=httpx.ConnectError("connection refused"))

    resposta = dentro.client.get(reverse("avisos"))

    assert MENSAGEM_DE_FALHA in resposta.content.decode()
    assert aviso.sugestao.titulo not in resposta.content.decode()


def test_falha_quando_a_rede_estoura_timeout(dentro, aviso, rede):
    rede.notificacoes_avisos.mock(side_effect=httpx.TimeoutException("demorou demais"))

    resposta = dentro.client.get(reverse("avisos"))

    assert MENSAGEM_DE_FALHA in resposta.content.decode()


def test_falha_quando_a_notificacoes_responde_500(dentro, aviso, rede):
    rede.notificacoes_avisos.mock(return_value=httpx.Response(500))

    resposta = dentro.client.get(reverse("avisos"))

    assert MENSAGEM_DE_FALHA in resposta.content.decode()


def test_falha_quando_a_notificacoes_responde_json_invalido(dentro, aviso, rede):
    rede.notificacoes_avisos.mock(
        return_value=httpx.Response(200, content=b"isto nao e um JSON")
    )

    resposta = dentro.client.get(reverse("avisos"))

    assert MENSAGEM_DE_FALHA in resposta.content.decode()


def test_falha_quando_o_corpo_esta_fora_do_contrato(dentro, aviso, rede):
    """200 de verdade, JSON de verdade, sem o campo `itens` que o contrato
    promete — 2xx não é sucesso (RETROSPECTIVA-FASE-D §4)."""
    rede.notificacoes_avisos.mock(return_value=httpx.Response(200, json={}))

    resposta = dentro.client.get(reverse("avisos"))

    assert MENSAGEM_DE_FALHA in resposta.content.decode()


def test_falha_sem_configuracao_e_nem_tenta_a_rede(dentro, aviso, rede, monkeypatch):
    monkeypatch.delenv("NOTIFICACOES_API_URL", raising=False)

    resposta = dentro.client.get(reverse("avisos"))

    assert MENSAGEM_DE_FALHA in resposta.content.decode()
    assert _chamadas(rede, "/avisos") == []


@pytest.fixture
def outra_pessoa(entrar_como):
    return entrar_como(email="bianca@exemplo.test", nome="Bianca")


# ---------------------------------------------------------------------------
# 2. N+1 — o título de cada sugestão citada, em UMA consulta
# ---------------------------------------------------------------------------
def _outra_sugestao(quadro, categoria, autor, titulo):
    return Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=autor,
        titulo=titulo,
        problema="Assisto no ônibus e não dá para ouvir.",
    )


def test_os_titulos_das_sugestoes_saem_em_uma_consulta_so(
    dentro, quadro, categoria, aluno
):
    """A página com 1 sugestão citada e a página com 6 fazem o MESMO número
    de consultas — comparação de dois números medidos, nunca um número
    cravado (a mesma disciplina de `tests/test_volume_dos_avisos.py`)."""

    contador = iter(range(100))

    def _semear(quantas: int) -> None:
        for _ in range(quantas):
            n = next(contador)
            sugestao = _outra_sugestao(quadro, categoria, aluno, f"Ideia numero {n}")
            Aviso.objects.create(
                destinatario=dentro.identidade,
                sugestao=sugestao,
                status_anterior=Sugestao.Status.EM_ANALISE,
                status_novo=Sugestao.Status.PLANEJADO,
                vinculo=Aviso.Vinculo.VOTO,
            )

    def _abrir():
        resposta = dentro.client.get(reverse("avisos"))
        assert resposta.status_code == 200
        return resposta

    _semear(1)
    limpar_cache_de_resumo()  # o sino no trilho tem cache próprio — ver o
    # comentário gêmeo em test_volume_dos_avisos.py::test_ler_a_pagina...
    with CaptureQueriesContext(connection) as com_uma:
        _abrir()

    _semear(5)
    limpar_cache_de_resumo()
    with CaptureQueriesContext(connection) as com_seis:
        resposta = _abrir()

    assert len(com_uma) == len(com_seis), (
        f"a página de avisos passou de {len(com_uma)} para {len(com_seis)} "
        "consultas ao crescer de 1 para 6 sugestões citadas — os títulos "
        "precisam sair de um `Sugestao.objects.filter(pk__in=...)` só.\n"
        + "\n".join(c["sql"] for c in com_seis.captured_queries)
    )
    culpadas = [
        c["sql"] for c in com_seis.captured_queries if "sugestoes_sugestao" in c["sql"]
    ]
    assert len(culpadas) == 1, (
        f"esperava 1 consulta em sugestoes_sugestao, vieram {len(culpadas)}: "
        f"{culpadas}"
    )
    corpo = resposta.content.decode()
    for n in range(6):
        assert (
            f"Ideia numero {n}" in corpo
        ), f"faltou o título da sugestão {n}: {corpo[-800:]}"


# ---------------------------------------------------------------------------
# 3. `vinculo` ausente (carta anterior a 27/08/2026) — nunca uma exceção
# ---------------------------------------------------------------------------
def test_vinculo_ausente_na_carta_nao_quebra_a_pagina(dentro, sugestao, rede):
    """Encena uma carta ANTIGA (sem `parametros.vinculo`) sobrescrevendo a
    resposta de `GET /avisos` à mão — o dublê fiel ao `Aviso` local sempre
    preenche `vinculo` (a coluna nunca é vazia), então só uma resposta
    fabricada consegue encenar o caso que o contrato declara opcional."""
    rede.notificacoes_avisos.mock(
        return_value=httpx.Response(
            200,
            json={
                "itens": [
                    {
                        "id": "carta-antiga-1",
                        "assunto": "sugestao.status-alterado",
                        "parametros": {
                            "suggestion_id": str(sugestao.pk),
                            "status_anterior": "em_analise",
                            "status_novo": "planejado",
                            # sem "vinculo" de propósito — carta de antes do
                            # campo existir.
                        },
                        "ator_id": None,
                        "lido_em": None,
                        "criado_em": "2026-08-20T12:00:00+00:00",
                    }
                ],
                "proximo_cursor": None,
            },
        )
    )

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert sugestao.titulo in corpo
    assert "aviso-vinculo" not in corpo, (
        "o selo de vínculo apareceu mesmo sem o campo na carta — devia ficar "
        "de fora, nunca inventar um rótulo."
    )


# ---------------------------------------------------------------------------
# 4. `marcar_lido`/`marcar_tudo_lido` — o payload certo, chegando de verdade
# ---------------------------------------------------------------------------
def test_marcar_lido_chama_marcar_lida_com_o_id_certo(dentro, quadro, aviso, rede):
    resposta = dentro.client.post(reverse("marcar_aviso_lido", args=[str(aviso.pk)]))

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("avisos")
    chamada = _chamadas(rede, "/marcar-lida")[-1].request
    corpo = json.loads(chamada.content)
    assert corpo == {
        "destinatario_id": dentro.identidade.id_da_plataforma,
        "site_id": quadro.site_id,
        "id": str(aviso.pk),
    }
    assert (
        chamada.headers["authorization"] == "Bearer token-do-par-sugestoes-notificacoes"
    )


def test_marcar_lido_e_idempotente_do_lado_da_notificacoes(dentro, aviso):
    primeira = dentro.client.post(reverse("marcar_aviso_lido", args=[str(aviso.pk)]))
    aviso.refresh_from_db()
    carimbo = aviso.lido_em
    assert carimbo is not None

    segunda = dentro.client.post(reverse("marcar_aviso_lido", args=[str(aviso.pk)]))
    aviso.refresh_from_db()

    assert primeira.status_code == segunda.status_code == 302
    assert aviso.lido_em == carimbo


def test_marcar_lido_com_notificacoes_fora_do_ar_nao_quebra_e_nao_marca(
    dentro, aviso, rede
):
    """A falha aqui não é 404 (não é "esse id não existe") — é "não sei", e a
    resposta é a mesma tolerância silenciosa do sino: a pessoa volta para a
    lista, e a PRÓXIMA leitura é quem avisa de verdade, se a falha persistir.
    """
    rede.notificacoes_marcar_lida.mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    resposta = dentro.client.post(reverse("marcar_aviso_lido", args=[str(aviso.pk)]))

    assert resposta.status_code == 302
    aviso.refresh_from_db()
    assert aviso.lido_em is None


def test_marcar_tudo_lido_chama_marcar_lidas_com_destinatario_e_site(
    dentro, quadro, categoria, equipe, rede
):
    """`dentro` precisa ser INTERESSADO nas sugestões — por isso as duas
    nascem com ele como autor (o jeito mais direto de virar destinatário de
    um aviso), em vez de reaproveitar a fixture `sugestao` (autoria de
    `aluno`, outra pessoa)."""
    from apps.core.moderacao import registrar_mudanca_de_status

    primeira = _outra_sugestao(quadro, categoria, dentro.identidade, "Ideia 1")
    segunda = _outra_sugestao(quadro, categoria, dentro.identidade, "Ideia 2")
    for sugestao in (primeira, segunda):
        registrar_mudanca_de_status(
            sugestao=sugestao,
            status_novo=Sugestao.Status.PLANEJADO,
            nota="",
            por=equipe.identidade,
        )
    assert (
        Aviso.objects.filter(
            destinatario=dentro.identidade, lido_em__isnull=True
        ).count()
        == 2
    )

    resposta = dentro.client.post(reverse("marcar_todos_avisos_lidos"))

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("avisos")
    chamada = _chamadas(rede, "/marcar-lidas")[-1].request
    corpo = json.loads(chamada.content)
    assert corpo == {
        "destinatario_id": dentro.identidade.id_da_plataforma,
        "site_id": quadro.site_id,
    }
    assert (
        Aviso.objects.filter(
            destinatario=dentro.identidade, lido_em__isnull=True
        ).count()
        == 0
    )
