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
from urllib.parse import quote

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
        "apagada": False,
        # A ficha da assinatura (TAR-023). Vazia por padrão — é assim que a
        # Caixa responde uma ideia que ninguém assinou. O campo é OPCIONAL no
        # contrato, e há um guarda para a tela aguentar ele não vir.
        "changespecs": [],
        # O rastro das correcoes de texto (31/08/2026). Vazio por padrao: e
        # assim que a Caixa responde uma ideia em que ninguem mexeu. Opcional
        # no contrato, e ha guarda para a tela aguentar ele nao vir.
        "correcoes": [],
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
# A FICHA da assinatura (TAR-023) — "está assinada?" e "com base em quê?"
# ---------------------------------------------------------------------------
#
# Até 30/08/2026 esta tela conhecia um booleano só. Ela deixava ASSINAR e não
# deixava CONFERIR o que foi assinado — a última das cinco telas de
# `/forms/sugestoes/moderacao` sem substituta aqui, e o que travava a
# aposentadoria delas (TAR-014).


def uma_ficha(**campos) -> dict:
    ficha = {
        "change_id": "CS-PORTFOLIO-0001",
        "documento": "docs/changespecs/CS-PORTFOLIO-0001.md",
        "aprovado_por": "Davi (mantenedor)",
        "aprovado_em": "2026-08-25",
        "registrado_por": "Davi",
        "registrado_em": "2026-08-25T18:30:00+00:00",
    }
    ficha.update(campos)
    return ficha


@respx.mock
def test_a_ficha_da_assinatura_aparece_inteira_na_tela():
    """Os quatro fatos que só existiam na tela velha da Caixa."""
    cliente = _dentro()
    a_caixa_conta(uma_ideia(tem_changespec=True, changespecs=[uma_ficha()]))

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert "CS-PORTFOLIO-0001" in pagina
    assert "docs/changespecs/CS-PORTFOLIO-0001.md" in pagina
    assert "Davi (mantenedor)" in pagina
    assert "2026-08-25" in pagina


@respx.mock
def test_a_ficha_mostra_TODAS_as_versoes_assinadas():
    """Escopo que mudou nasce `-v2`; mostrar só a última esconderia a corrente."""
    cliente = _dentro()
    a_caixa_conta(
        uma_ideia(
            tem_changespec=True,
            changespecs=[
                uma_ficha(change_id="CS-PORTFOLIO-0001-v2"),
                uma_ficha(change_id="CS-PORTFOLIO-0001"),
            ],
        )
    )

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert "CS-PORTFOLIO-0001-v2" in pagina
    assert pagina.index("CS-PORTFOLIO-0001-v2") < pagina.rindex("CS-PORTFOLIO-0001")


@respx.mock
def test_o_documento_que_e_URL_vira_link_e_o_caminho_do_repo_nao():
    """Um `href` relativo levaria a um 404 com cara de link quebrado do Admin."""
    cliente = _dentro()
    a_caixa_conta(
        uma_ideia(
            tem_changespec=True,
            changespecs=[uma_ficha(documento="https://exemplo.test/cs-1")],
        )
    )

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert '<a href="https://exemplo.test/cs-1"' in pagina


@respx.mock
def test_quem_assina_continua_podendo_registrar_uma_versao_nova():
    """Assinada não é o fim: `-v2` existe, e sem esta tela ele fica sem porta.

    A tela velha listava e oferecia o formulário na mesma página; esconder o
    formulário depois da primeira assinatura tiraria da plataforma a única
    forma de registrar a versão seguinte no dia em que ela for aposentada.
    """
    cliente = _dentro()
    a_caixa_conta(uma_ideia(tem_changespec=True, changespecs=[uma_ficha()]))

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert reverse("caixa_assinar", args=[7]) in pagina
    assert "-v2" in pagina


@respx.mock
def test_a_tela_aguenta_a_ficha_ausente():
    """`changespecs` é opcional no contrato — a Caixa de ontem não o manda."""
    cliente = _dentro()
    corpo = uma_ideia(tem_changespec=True)
    del corpo["changespecs"]
    a_caixa_conta(corpo)

    resposta = cliente.get(reverse("caixa_ideia", args=[7]))

    assert resposta.status_code == 200
    assert "já está assinada" in texto(resposta)


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


@pytest.mark.parametrize(
    "campo,valor,rotulo",
    [
        ("impacto_educacional", "99", "Ajuda o aluno a aprender"),
        ("impacto_comercial", "-3", "Ajuda a escola a vender"),
        ("esforco_tecnico", "x", "Trabalho que dá"),
    ],
)
@respx.mock
def test_uma_nota_fora_da_escala_e_RECUSADA_e_nada_e_guardado(campo, valor, rotulo):
    """Arredondar em silêncio escreve outra coisa no lugar do que a pessoa quis.

    Até 30/08/2026 esta tela fazia `max(0, min(5, ...))`: quem digitasse 99 via
    "Avaliação guardada" com um 5 gravado, e quem digitasse "x" via um 0. A tela
    velha da Caixa recusava com uma frase em português — e é ela que fica, agora
    daqui: falso-verde de produto (`RETROSPECTIVA-FASE-D` §1) é a resposta de
    sucesso descrevendo um dado que ninguém pediu.
    """
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/avaliacao").mock(
        return_value=httpx.Response(200, json=uma_ideia())
    )

    resposta = cliente.post(
        reverse("caixa_avaliar", args=[7]),
        {"impacto_educacional": "4", "impacto_comercial": "4", "esforco_tecnico": "4"}
        | {campo: valor},
    )

    assert resposta.status_code == 302
    assert not escrita.called, "nota fora da escala não podia nem sair daqui"
    assert "erro=" in resposta["Location"]
    assert quote(rotulo).replace("%20", "+") in resposta["Location"]


@respx.mock
def test_a_nota_em_branco_continua_valendo_zero():
    """O formulário sai da tela com campos vazios; vazio é 0, não é recusa."""
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/avaliacao").mock(
        return_value=httpx.Response(200, json=uma_ideia())
    )

    cliente.post(reverse("caixa_avaliar", args=[7]), {"notas": "só um bilhete"})

    enviado = json.loads(escrita.calls.last.request.content)
    assert enviado["impacto_educacional"] == 0
    assert enviado["notas"] == "só um bilhete"


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
        "caixa_apagar",
        "caixa_corrigir",
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
        "caixa_apagar",
        "caixa_corrigir",
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


# ---------------------------------------------------------------------------
# Apagar definitivamente — `DECISAO-apagar-ideia.md` (29/08/2026)
# ---------------------------------------------------------------------------


@respx.mock
def test_apagar_manda_quem_agiu():
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/apagar").mock(
        return_value=httpx.Response(
            200, json=uma_ideia(apagada=True, arquivada=True, titulo="", problema="")
        )
    )

    resposta = cliente.post(reverse("caixa_apagar", args=[7]), {})

    assert resposta.status_code == 302
    enviado = json.loads(escrita.calls.last.request.content)
    assert enviado["por_email"] == DONO
    assert enviado["por_id_da_plataforma"] == ID_DA_PLATAFORMA


@respx.mock
def test_apagar_ja_apagada_mostra_a_recusa_da_caixa():
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/apagar").mock(
        return_value=httpx.Response(422, json={"erro": "Esta ideia já foi apagada."})
    )

    resposta = cliente.post(reverse("caixa_apagar", args=[7]), {})

    assert "erro=" in resposta["Location"]
    assert "j%C3%A1+foi+apagada" in resposta["Location"]


@respx.mock
def test_a_tela_mostra_o_aviso_definitivo_e_esconde_tudo_quando_apagada():
    cliente = _dentro()
    a_caixa_conta(uma_ideia(apagada=True, arquivada=True, titulo="", problema=""))

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert "apagada definitivamente" in pagina
    assert "Não há como restaurar" in pagina
    assert reverse("caixa_desarquivar", args=[7]) not in pagina
    assert reverse("caixa_arquivar", args=[7]) not in pagina
    assert reverse("caixa_apagar", args=[7]) not in pagina
    assert "Mover de fase" not in pagina


@respx.mock
def test_a_tela_oferece_apagar_quando_nao_esta_apagada():
    cliente = _dentro()
    a_caixa_conta()

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert reverse("caixa_apagar", args=[7]) in pagina


@respx.mock
def test_apagar_deixa_rastro_na_auditoria():
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/apagar").mock(
        return_value=httpx.Response(200, json=uma_ideia(apagada=True, arquivada=True))
    )

    cliente.post(reverse("caixa_apagar", args=[7]), {})

    linha = Registro.objects.get()
    assert linha.acao == Registro.APAGAR_IDEIA
    assert linha.desfecho == Registro.OK
    assert linha.alvo == "ideia:7"


# ---------------------------------------------------------------------------
# Corrigir o texto — `DECISAO-corrigir-o-texto-de-uma-ideia.md` (31/08/2026)
# ---------------------------------------------------------------------------


@respx.mock
def test_corrigir_manda_os_tres_campos_e_quem_agiu():
    """Os três inteiros, não só o que mudou: quem compara é a Caixa.

    Fazer a conta aqui seria a tela decidir, com o texto que a página carregou
    minutos atrás, uma coisa que só a dona do dado sabe agora.
    """
    cliente = _dentro()
    a_caixa_conta()
    escrita = respx.post(f"{IDEIAS}/7/texto").mock(
        return_value=httpx.Response(200, json=uma_ideia(titulo="Tutorial de cabelo"))
    )

    resposta = cliente.post(
        reverse("caixa_corrigir", args=[7]),
        {
            "titulo": "Tutorial de cabelo",
            "problema": "Meus projetos ficam parados no computador.",
            "solucao_proposta": "",
        },
    )

    assert resposta.status_code == 302
    enviado = json.loads(escrita.calls.last.request.content)
    assert enviado["titulo"] == "Tutorial de cabelo"
    assert enviado["problema"] == "Meus projetos ficam parados no computador."
    assert enviado["solucao_proposta"] == ""
    assert enviado["por_email"] == DONO
    assert enviado["por_id_da_plataforma"] == ID_DA_PLATAFORMA


@respx.mock
def test_a_recusa_de_texto_igual_chega_inteira_ao_operador():
    """A frase é da Caixa. Reescrevê-la aqui daria duas redações para a mesma
    recusa, e a que ninguém testa é a que fica errada."""
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/texto").mock(
        return_value=httpx.Response(
            422,
            json={"erro": "Não havia nada para mudar: o texto enviado é igual."},
        )
    )

    resposta = cliente.post(
        reverse("caixa_corrigir", args=[7]),
        {"titulo": "Página pública com os meus projetos", "problema": "x"},
    )

    assert "erro=" in resposta["Location"]
    assert "nada+para+mudar" in resposta["Location"]


@respx.mock
def test_corrigir_deixa_rastro_na_auditoria_com_verbo_proprio():
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/texto").mock(
        return_value=httpx.Response(200, json=uma_ideia())
    )

    cliente.post(reverse("caixa_corrigir", args=[7]), {"titulo": "x", "problema": "y"})

    linha = Registro.objects.get()
    assert linha.acao == Registro.CORRIGIR_IDEIA
    assert linha.desfecho == Registro.OK
    assert linha.alvo == "ideia:7"


@respx.mock
def test_a_recusa_da_caixa_tambem_deixa_rastro():
    """O desfecho RECUSADO é o que justifica esta tabela existir: quando a Caixa
    diz não, nada é escrito lá — e mexer no texto de um aluno não pode ser um
    gesto sem rastro em lugar nenhum."""
    cliente = _dentro()
    a_caixa_conta()
    respx.post(f"{IDEIAS}/7/texto").mock(
        return_value=httpx.Response(422, json={"erro": "O nome não pode ficar vazio."})
    )

    cliente.post(reverse("caixa_corrigir", args=[7]), {"titulo": "  ", "problema": "y"})

    linha = Registro.objects.get()
    assert linha.acao == Registro.CORRIGIR_IDEIA
    assert linha.desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
def test_o_formulario_vem_preenchido_com_o_texto_de_agora():
    """É o que faz o gesto ser um conserto, e não um recomeço."""
    cliente = _dentro()
    a_caixa_conta(
        uma_ideia(
            titulo="Turorial de cabelo avançado masculino",
            problema="Queria um turorial mais avançado.",
        )
    )

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert reverse("caixa_corrigir", args=[7]) in pagina
    assert 'value="Turorial de cabelo avançado masculino"' in pagina
    assert "Queria um turorial mais avançado." in pagina
    assert "sem nenhuma marca" in pagina, (
        "quem corrige precisa saber, ANTES de apertar o botão, que o aluno não "
        "vê marca nenhuma"
    )


@respx.mock
def test_o_rastro_aparece_com_o_texto_anterior_e_o_campo_em_portugues():
    cliente = _dentro()
    a_caixa_conta(
        uma_ideia(
            titulo="Tutorial de cabelo",
            correcoes=[
                {
                    "quando": "2026-08-31T18:00:00+00:00",
                    "campo": "titulo",
                    "antes": "Turorial de cabelo",
                    "depois": "Tutorial de cabelo",
                    "por": "Davi",
                }
            ],
        )
    )

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert "o nome da ideia" in pagina, "o rastro mostra nome de campo cru"
    assert "Turorial de cabelo" in pagina
    assert "Davi" in pagina


@respx.mock
def test_a_tela_aguenta_o_rastro_ausente():
    """`correcoes` é opcional no contrato: a Caixa de ontem não manda a chave."""
    cliente = _dentro()
    ideia = uma_ideia()
    del ideia["correcoes"]
    a_caixa_conta(ideia)

    pagina = cliente.get(reverse("caixa_ideia", args=[7]))

    assert pagina.status_code == 200
    assert reverse("caixa_corrigir", args=[7]) in texto(pagina)


@respx.mock
def test_a_ideia_apagada_nao_oferece_corrigir():
    """Corrigir o texto de uma ideia apagada traria de volta, por uma porta
    lateral, o conteúdo que o apagar prometeu destruir."""
    cliente = _dentro()
    a_caixa_conta(uma_ideia(apagada=True, arquivada=True, titulo="", problema=""))

    pagina = texto(cliente.get(reverse("caixa_ideia", args=[7])))

    assert reverse("caixa_corrigir", args=[7]) not in pagina
