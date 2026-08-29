"""As três ações da Caixa, feitas de dentro do Admin (28/08/2026).

Lei: `docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`. Mover de fase,
escrever a avaliação e assinar a obra saíram das telas da Caixa e passaram a
acontecer daqui — pelo contrato, e com as travas todas continuando do outro lado.

O que estes guardas protegem:

1. **A ação chega à Caixa na forma que ela pede** — inclusive o identificador de
   quem age, que `[INV-SUG12]` exige para o fato poder ser afirmado.
2. **A recusa da Caixa chega inteira ao operador.** A frase que ela devolve
   ENSINA o caminho; reescrevê-la aqui daria duas redações para a mesma recusa,
   e a que ninguém testa é a que fica errada.
3. **A auditoria acontece nos três desfechos.** É o desfecho RECUSADO que
   justifica esta tabela existir: quando a Caixa diz não, nada é escrito lá — sem
   a linha daqui, o gesto não teria deixado rastro em lugar nenhum.
4. **A assinatura não aparece para quem não assina**, e a tela explica por quê
   em vez de mostrar um botão morto.
"""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CAIXA = "http://sugestoes:8000/interno"
IDEIAS = f"{CAIXA}/gestao/ideias"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ID_DA_PLATAFORMA = "id-opaco-123"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("SUGESTOES_API_URL", CAIXA)
    monkeypatch.setenv("SUGESTOES_API_TOKEN", "token-do-par-admin-sugestoes")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": ID_DA_PLATAFORMA,
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def uma_ideia(**campos) -> dict:
    base = {
        "id": 7,
        "titulo": "Página pública com os meus projetos",
        "problema": "Meus projetos ficam parados no computador.",
        "solucao_proposta": "",
        "categoria": "Plataforma",
        "status": "planejado",
        "votos": 218,
        "comentarios": 31,
        "pessoas": 176,
        "autor": "Larissa M.",
        "criada_em": "2026-07-12T10:00:00+00:00",
        "parada_desde": "2026-07-12T10:00:00+00:00",
        "ja_ouviram": True,
        "tem_avaliacao": False,
        "tem_changespec": False,
        "motivo_da_saida": "",
        "avaliacao": None,
        "arquivada": False,
        "arquivada_em": "",
        "motivo_do_arquivamento": "",
        "historico": [
            {
                "quando": "2026-08-14T09:00:00+00:00",
                "de": "em_analise",
                "para": "planejado",
                "nota": "vai entrar",
                "por": "Fulano",
            }
        ],
    }
    base.update(campos)
    return base


def a_caixa_conta(ideia=None, **topo):
    corpo = ideia or uma_ideia()
    respx.get(f"{IDEIAS}/7").mock(return_value=httpx.Response(200, json=corpo))
    lista = {
        "quadro": "Meshcraft",
        "pode_assinar": True,
        "pessoas_esperando": 176,
        "silencio_medio_em_dias": 14,
        "pessoas_em_silencio_demais": 0,
        "ideias": [{k: v for k, v in corpo.items() if k != "historico"}],
    }
    lista.update(topo)
    respx.get(IDEIAS).mock(return_value=httpx.Response(200, json=lista))


def texto(resposta) -> str:
    return resposta.content.decode()


# ---------------------------------------------------------------------------
# A tela de uma ideia
# ---------------------------------------------------------------------------


@respx.mock
def test_a_ideia_mostra_a_historia_dela():
    """Sem esta tela, a história ficaria inalcançável ao aposentar as antigas."""
    cliente = _dentro()
    a_caixa_conta()

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert "A história desta ideia" in pagina
    assert "vai entrar" in pagina
    assert "em_analise &rarr; planejado" in pagina or "em_analise → planejado" in pagina
    assert "nunca é editado" in pagina


@respx.mock
def test_a_ideia_que_a_caixa_nao_conta_nao_vira_tela_quebrada():
    cliente = _dentro()
    respx.get(f"{IDEIAS}/7").mock(return_value=httpx.Response(404, json={}))
    respx.get(IDEIAS).mock(return_value=httpx.Response(200, json={"ideias": []}))

    resposta = cliente.get(reverse("caixa_ideia", args=[7]))

    assert resposta.status_code == 200
    assert "Não consegui perguntar" in texto(resposta)


@respx.mock
def test_quem_nao_assina_ve_a_explicacao_e_nao_um_botao_morto():
    """Botão desabilitado protege a tela, não a regra — e não ensina nada."""
    cliente = _dentro()
    a_caixa_conta(pode_assinar=False)

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert reverse("caixa_assinar", args=[7]) not in pagina
    assert "Só quem está na lista de aprovadores" in pagina


@respx.mock
def test_quem_assina_ve_o_formulario():
    cliente = _dentro()
    a_caixa_conta()

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert reverse("caixa_assinar", args=[7]) in pagina
    assert "Assinar e liberar a obra" in pagina


# ---------------------------------------------------------------------------
# As três ações
# ---------------------------------------------------------------------------


@respx.mock
def test_mover_manda_quem_age_junto():
    """[INV-SUG12]: sem o identificador de quem agiu, a Caixa não afirma o fato."""
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/status").mock(
        return_value=httpx.Response(200, json=uma_ideia(status="implementado"))
    )

    resposta = cliente.post(
        reverse("caixa_mover", args=[7]), {"fase": "implementado", "nota": "no ar"}
    )

    assert resposta.status_code == 302
    enviado = json.loads(escrita.calls.last.request.content)
    assert enviado["status"] == "implementado"
    assert enviado["por_email"] == DONO
    assert enviado["por_id_da_plataforma"] == ID_DA_PLATAFORMA


@respx.mock
def test_uma_fase_fora_da_lista_nao_chega_a_sair_daqui():
    """`mesclado` não está no leque da equipe; a tela nem tenta."""
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/status").mock(
        return_value=httpx.Response(200, json=uma_ideia())
    )

    resposta = cliente.post(reverse("caixa_mover", args=[7]), {"fase": "mesclado"})

    assert resposta.status_code == 302
    assert not escrita.called
    assert "erro=" in resposta["Location"]


@respx.mock
def test_a_recusa_da_caixa_chega_inteira_ao_operador():
    """A frase que a Caixa devolve ENSINA o caminho; reescrevê-la daria duas."""
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/status").mock(
        return_value=httpx.Response(
            422,
            json={"erro": "Para dizer que a ideia não será feita, escreva o porquê"},
        )
    )

    resposta = cliente.post(
        reverse("caixa_mover", args=[7]), {"fase": "nao_planejado", "nota": ""}
    )

    assert resposta.status_code == 302
    assert "escreva+o+porqu" in resposta["Location"]


@respx.mock
def test_avaliar_manda_os_cinco_campos():
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/avaliacao").mock(
        return_value=httpx.Response(200, json=uma_ideia(tem_avaliacao=True))
    )

    cliente.post(
        reverse("caixa_avaliar", args=[7]),
        {
            "impacto_educacional": "4",
            "impacto_comercial": "5",
            "esforco_tecnico": "3",
            "decisao_produto": "Modelo fixo.",
            "notas": "cabe",
        },
    )

    enviado = json.loads(escrita.calls.last.request.content)
    assert enviado["impacto_comercial"] == 5
    assert enviado["decisao_produto"] == "Modelo fixo."


@respx.mock
def test_uma_nota_absurda_e_aparada_antes_de_sair():
    """Zero a cinco é a escala da Caixa; mandar 99 daria recusa por formulário."""
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/avaliacao").mock(
        return_value=httpx.Response(200, json=uma_ideia())
    )

    cliente.post(
        reverse("caixa_avaliar", args=[7]),
        {
            "impacto_educacional": "99",
            "impacto_comercial": "-3",
            "esforco_tecnico": "x",
        },
    )

    enviado = json.loads(escrita.calls.last.request.content)
    assert enviado["impacto_educacional"] == 5, "99 tinha de virar 5"
    assert enviado["impacto_comercial"] == 0, "negativo tinha de virar 0"
    assert enviado["esforco_tecnico"] == 0, "texto tinha de virar 0"


@respx.mock
def test_assinar_manda_o_documento_e_quem_assinou():
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/changespec").mock(
        return_value=httpx.Response(200, json=uma_ideia(tem_changespec=True))
    )

    cliente.post(
        reverse("caixa_assinar", args=[7]),
        {
            "change_id": "CS-PORTFOLIO-0001",
            "documento": "docs/changespecs/CS-PORTFOLIO-0001.md",
            "aprovado_por": "Davi",
            "aprovado_em": "2026-08-28",
        },
    )

    enviado = json.loads(escrita.calls.last.request.content)
    assert enviado["change_id"] == "CS-PORTFOLIO-0001"
    assert enviado["aprovado_por"] == "Davi"


@respx.mock
def test_a_recusa_do_aprovador_chega_com_a_frase_da_caixa():
    """Estar no Admin não dá o direito de assinar — e a Caixa é quem recusa."""
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/changespec").mock(
        return_value=httpx.Response(
            403, json={"erro": "Só quem está na lista de aprovadores da Caixa autoriza"}
        )
    )

    resposta = cliente.post(
        reverse("caixa_assinar", args=[7]),
        {
            "change_id": "CS-X-0001",
            "documento": "docs/changespecs/CS-X-0001.md",
            "aprovado_por": "Alguém",
            "aprovado_em": "2026-08-28",
        },
    )

    assert "erro=" in resposta["Location"]
    assert "aprovadores" in resposta["Location"]


# ---------------------------------------------------------------------------
# A auditoria — nos TRÊS desfechos
# ---------------------------------------------------------------------------


@respx.mock
def test_a_acao_que_deu_certo_deixa_rastro():
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/status").mock(
        return_value=httpx.Response(200, json=uma_ideia())
    )

    cliente.post(reverse("caixa_mover", args=[7]), {"fase": "implementado"})

    linha = Registro.objects.get()
    assert linha.acao == Registro.MOVER_IDEIA
    assert linha.desfecho == Registro.OK
    assert linha.alvo == "ideia:7:implementado"
    assert linha.quem_email == DONO


@respx.mock
def test_a_acao_RECUSADA_tambem_deixa_rastro():
    """É este desfecho que justifica a tabela existir.

    Quando a Caixa diz não, nada é escrito lá. Sem esta linha, a tentativa não
    teria deixado rastro em lugar nenhum — e uma tentativa recusada é
    exatamente o que alguém vai querer auditar depois.
    """
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/changespec").mock(
        return_value=httpx.Response(403, json={"erro": "não é aprovador"})
    )

    cliente.post(
        reverse("caixa_assinar", args=[7]),
        {
            "change_id": "CS-X-0001",
            "documento": "docs/changespecs/CS-X-0001.md",
            "aprovado_por": "Alguém",
            "aprovado_em": "2026-08-28",
        },
    )

    linha = Registro.objects.get()
    assert linha.acao == Registro.ASSINAR_OBRA
    assert linha.desfecho == Registro.RECUSADO_PELA_CELULA
    assert "aprovador" in linha.detalhe


@respx.mock
def test_a_caixa_fora_do_ar_tambem_deixa_rastro():
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/avaliacao").mock(side_effect=httpx.ConnectError("caiu"))

    cliente.post(reverse("caixa_avaliar", args=[7]), {"impacto_educacional": "3"})

    linha = Registro.objects.get()
    assert linha.acao == Registro.AVALIAR_IDEIA
    assert linha.desfecho == Registro.NAO_RESPONDEU


@pytest.mark.parametrize(
    "rota",
    [
        "caixa_mover",
        "caixa_avaliar",
        "caixa_assinar",
        "caixa_arquivar",
        "caixa_desarquivar",
    ],
)
def test_as_acoes_recusam_GET(rota):
    """Um GET seria disparado por qualquer pré-carregamento de link do navegador."""
    resposta = _dentro_sem_rede().get(reverse(rota, args=[7]))

    assert resposta.status_code in (302, 405)


def _dentro_sem_rede() -> Client:
    """Um cliente sem sessão: a porta responde antes de qualquer chamada."""
    return Client()


@pytest.mark.parametrize(
    "rota",
    [
        "caixa_ideia",
        "caixa_mover",
        "caixa_avaliar",
        "caixa_assinar",
        "caixa_arquivar",
        "caixa_desarquivar",
    ],
)
def test_sem_sessao_nenhuma_rota_nova_responde(rota):
    resposta = Client().get(reverse(rota, args=[7]))

    assert resposta.status_code == 302
    assert "/entrar/google" in resposta["Location"]


# ---------------------------------------------------------------------------
# Arquivar — `DECISAO-arquivar-ideia.md` (29/08/2026)
# ---------------------------------------------------------------------------


@respx.mock
def test_arquivar_manda_o_motivo_e_quem_agiu():
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/arquivar").mock(
        return_value=httpx.Response(200, json=uma_ideia(arquivada=True))
    )

    resposta = cliente.post(
        reverse("caixa_arquivar", args=[7]), {"motivo": "duplicata da #12"}
    )

    assert resposta.status_code == 302
    enviado = json.loads(escrita.calls.last.request.content)
    assert enviado["motivo"] == "duplicata da #12"
    assert enviado["por_email"] == DONO
    assert enviado["por_id_da_plataforma"] == ID_DA_PLATAFORMA


@respx.mock
def test_arquivar_ja_arquivada_mostra_a_recusa_da_caixa():
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/arquivar").mock(
        return_value=httpx.Response(422, json={"erro": "Esta ideia já está arquivada."})
    )

    resposta = cliente.post(reverse("caixa_arquivar", args=[7]), {})

    assert "erro=" in resposta["Location"]
    assert "j%C3%A1+est%C3%A1+arquivada" in resposta["Location"]


@respx.mock
def test_desarquivar_manda_quem_agiu():
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/desarquivar").mock(
        return_value=httpx.Response(200, json=uma_ideia(arquivada=False))
    )

    resposta = cliente.post(reverse("caixa_desarquivar", args=[7]), {})

    assert resposta.status_code == 302
    enviado = json.loads(escrita.calls.last.request.content)
    assert enviado["por_email"] == DONO
    assert enviado["por_id_da_plataforma"] == ID_DA_PLATAFORMA


@respx.mock
def test_a_tela_mostra_o_aviso_e_o_botao_de_restaurar_quando_arquivada():
    cliente = _dentro()
    a_caixa_conta(uma_ideia(arquivada=True, motivo_do_arquivamento="duplicata da #12"))

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert "está arquivada" in pagina
    assert "duplicata da #12" in pagina
    assert reverse("caixa_desarquivar", args=[7]) in pagina
    assert reverse("caixa_arquivar", args=[7]) not in pagina


@respx.mock
def test_a_tela_oferece_arquivar_quando_nao_esta_arquivada():
    cliente = _dentro()
    a_caixa_conta()

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert "está arquivada" not in pagina
    assert reverse("caixa_arquivar", args=[7]) in pagina


@respx.mock
def test_arquivar_deixa_rastro_na_auditoria():
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/arquivar").mock(
        return_value=httpx.Response(200, json=uma_ideia(arquivada=True))
    )

    cliente.post(reverse("caixa_arquivar", args=[7]), {"motivo": "spam"})

    linha = Registro.objects.get()
    assert linha.acao == Registro.ARQUIVAR_IDEIA
    assert linha.desfecho == Registro.OK
    assert linha.alvo == "ideia:7"
