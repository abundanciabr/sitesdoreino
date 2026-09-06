"""A lista dos recusados, e o botão de voltar atrás — pedido do mantenedor.

02/09/2026: *"Coloque a opção de ver a lista dos alunos RECUSADOS, com a opção
de os aceitar novamente."* O cartão "Recusados" da tela de alunos contava
pessoas desde que o par de tokens subiu, e não havia em lugar nenhum como saber
QUEM eram — um número que levanta a pergunta e não a responde.

O que este arquivo trava, e por que um teste de status não pegaria:

1. **O MOTIVO aparece.** É a única coisa capaz de responder "eu volto atrás?", e
   é justamente o campo que a lei da fila obriga a escrever na recusa. Uma ficha
   antiga sem motivo diz que não sabe, em vez de fingir que não houve motivo.

2. **Aceitar de novo NÃO abre porta nova na `alunos`.** São as duas portas que
   já existem, na ordem: o pedido volta para a fila (`POST /pre-matriculas`) e é
   liberado na sequência (`POST /pre-matriculas/{id}/decisao`).

3. **Os dados da pessoa são RELIDOS do lado da `alunos`, nunca do formulário.**
   Reenviar o pedido reescreve nome, WhatsApp, turma e data da compra — campos
   escondidos no HTML transformariam este botão numa porta de edição silenciosa
   do cadastro de quem está na fila.

4. **A falha do meio é visível e não repetível.** Se a liberação falhar, a tela
   diz ONDE a pessoa ficou (esperando na fila), em vez de um "não deu certo" que
   faria o mantenedor clicar de novo.

5. **"Não sei" nunca vira "não recusei ninguém"** — o mesmo invariante de
   `test_painel_da_escola.py`, e aqui ele é o que impede a tela de convencer o
   mantenedor de que não há ninguém esperando ser reconsiderado.

6. **Toda tentativa deixa linha de auditoria**, inclusive as que falharam, e com
   verbo PRÓPRIO: voltar atrás numa decisão dele mesmo é o gesto que os
   `liberar` não sabem contar.

7. **Apagar de vez é o oposto de reconsiderar, e é o único gesto irreversível
   desta escola** (03/09/2026,
   `docs/decisoes/DECISAO-apagar-recusado-definitivamente.md`). Reverte, só
   para quem nunca chegou a ser aluno, a lei de 29/08 que tirou a capacidade
   de apagar do sistema inteiro. Verbo PRÓPRIO na auditoria
   (`Registro.APAGAR_RECUSADO`), e nunca o `APAGAR` aposentado — que era sobre
   a ficha de um aluno, e continua impossível.
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
LISTA = f"{ALUNOS}/matriculas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

TELA = "/escola/alunos/recusados"
GESTO = "/escola/alunos/reconsiderar"
# [CURSO] Aceitar mesmo assim LIBERA, e liberar exige o curso desde 06/09/2026
# ([INV-ALU-C1]). Os testes daqui continuam medindo o gesto de dois passos e a
# auditoria dele; o que acontece SEM o curso mora em `test_liberar_com_curso.py`.
CURSO = "prod-primeiros-dolares"
GESTO_APAGAR = "/escola/alunos/recusados/apagar"


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": email,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _texto(resposta) -> str:
    return resposta.content.decode()


def _recusado(**campos) -> dict:
    corpo = {
        "id": "7",
        "site_id": "escola-a",
        "email": "ana@exemplo.com",
        "nome_completo": "Ana Paula",
        "whatsapp": "(96) 99999-0000",
        "comprou_em": None,
        "turma": None,
        "status": "recusada",
        "criada_em": "2026-08-20T10:00:00Z",
        "esperando_ha_dias": 13,
        "motivo_recusa": "não achei o pagamento",
        "ja_foi_aluno": False,
        "passagens_anteriores": 0,
        "saiu_em": None,
    }
    corpo.update(campos)
    return corpo


def _recusados_respondem(linhas):
    """Só a porta `status=recusada`. As outras não estão registradas aqui de
    propósito: `respx.mock` estoura se a view pedir a lista inteira de alunos
    ou a fila de quem espera, e é esse estouro que prova que ela não pede."""
    return respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=linhas)
    )


# ------------------------------------------------- 1. a lista, com o motivo


@respx.mock
def test_a_lista_mostra_quem_foi_recusado_e_o_motivo():
    _recusados_respondem(
        [
            _recusado(id="7", nome_completo="Ana Paula", motivo_recusa="sem pagamento"),
            _recusado(
                id="8",
                nome_completo="Bruno Reis",
                email="bruno@exemplo.com",
                motivo_recusa="pediu duas vezes",
            ),
        ]
    )
    html = _texto(_dentro().get(TELA))

    assert "Ana Paula" in html
    assert "Bruno Reis" in html
    assert "sem pagamento" in html
    assert "pediu duas vezes" in html


@respx.mock
def test_ficha_sem_motivo_diz_que_nao_ha_em_vez_de_ficar_muda():
    """Uma ficha antiga sem motivo não pode passar por "recusa sem razão": a
    tela diz que não há motivo escrito, e o mantenedor sabe que a ausência é da
    ficha, não da decisão dele."""
    _recusados_respondem([_recusado(motivo_recusa=None)])
    assert "Sem motivo escrito nesta ficha" in _texto(_dentro().get(TELA))


@respx.mock
def test_a_lista_pede_direto_o_filtro_recusada_e_nao_a_escola_inteira():
    """`contar_a_escola()` traria contagens e alunos que esta tela não usa. Se
    a view os pedisse, as rotas não registradas fariam `respx` estourar."""
    _recusados_respondem([_recusado()])
    r = _dentro().get(TELA)
    assert r.status_code == 200, r.content
    assert "Ana Paula" in _texto(r)


@respx.mock
def test_a_busca_filtra_a_lista_e_diz_quantos_de_quantos():
    _recusados_respondem(
        [
            _recusado(id="7", nome_completo="Ana Paula"),
            _recusado(id="8", nome_completo="Bruno Reis", email="bruno@exemplo.com"),
        ]
    )
    html = _texto(_dentro().get(f"{TELA}?q=bruno"))
    assert "Bruno Reis" in html
    assert "Ana Paula" not in html
    assert "Mostrando 1 de 2" in html


@respx.mock
def test_busca_sem_resultado_nao_diz_que_ninguem_foi_recusado():
    """Vazio por PENEIRA e vazio por AUSÊNCIA são frases diferentes: confundi-las
    faria o mantenedor fechar a página achando que não recusou ninguém."""
    _recusados_respondem([_recusado()])
    html = _texto(_dentro().get(f"{TELA}?q=zeca"))
    assert "Nenhum dos 1 recusados casou com a sua procura" in html
    assert "Você não recusou ninguém" not in html


@respx.mock
def test_o_whatsapp_nao_e_campo_de_busca():
    """O número é o dado mais sensível desta área (lei da fila §5), e uma busca
    que casasse com ele convidaria a colar telefones na barra de endereço."""
    _recusados_respondem([_recusado(whatsapp="(96) 98888-1111")])
    html = _texto(_dentro().get(f"{TELA}?q=98888"))
    assert "Ana Paula" not in html


# ------------------------------------------- 2. "não sei" nunca vira "zero"


@respx.mock
def test_zero_recusados_e_medido_e_diz_isso():
    _recusados_respondem([])
    html = _texto(_dentro().get(TELA))
    assert "Você não recusou ninguém" in html
    assert "Ainda não consigo ver quem foi recusado" not in html


@respx.mock
@pytest.mark.parametrize(
    "resposta,motivo",
    [
        (httpx.Response(401), "o par não está em TOKENS_ACEITOS_ADMIN"),
        (httpx.Response(500), "a alunos quebrou"),
    ],
)
def test_falha_ao_perguntar_nao_vira_lista_vazia(resposta, motivo):
    respx.get(FILA, params={"status": "recusada"}).mock(return_value=resposta)
    r = _dentro().get(TELA)
    assert r.status_code == 200, f"{motivo}: {r.content}"
    html = _texto(r)
    assert "Ainda não consigo ver quem foi recusado" in html
    assert "Você não recusou ninguém" not in html


@respx.mock
def test_sem_o_par_de_tokens_a_tela_diz_que_nao_consegue_ver(monkeypatch):
    monkeypatch.delenv("ALUNOS_API_URL", raising=False)
    monkeypatch.delenv("ALUNOS_API_TOKEN", raising=False)
    r = _dentro().get(TELA)
    assert r.status_code == 200
    assert "Ainda não consigo ver quem foi recusado" in _texto(r)


# ------------------------------------------------------- 3. atrás da porta


def test_sem_sessao_a_lista_vai_para_o_login():
    r = Client().get(TELA)
    assert r.status_code == 302
    assert r["Location"].startswith("/entrar/google?next=")


@respx.mock
def test_fora_da_lista_de_administradores_recebe_404():
    assert _dentro("estranho@exemplo.com").get(TELA).status_code == 404


@respx.mock
def test_o_gesto_recusa_GET():
    """Aceitar alguém por GET é aceitar alguém quando um pré-carregador de link
    ou um antivírus corporativo abrir a página."""
    assert _dentro().get(GESTO).status_code == 405


# ----------------------------------------------- 4. o link no cartão certo


@respx.mock
def test_o_link_esta_dentro_do_cartao_de_recusados():
    """O endereço aparece DEPOIS do rótulo "Recusados" — não solto em outro
    lugar da página, que passaria neste teste por engano se a asserção fosse
    só `in html`."""
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=[]))

    html = _texto(_dentro().get("/escola/alunos/"))
    assert reverse("escola_recusados") in html[html.index("Recusados") :]


@respx.mock
def test_o_mapa_da_jornada_manda_o_recusado_para_a_lista_certa():
    """Antes desta tela, a parada "Recusado" do mapa dizia "Ver na fila" e caía
    em `/escola/alunos/` — a lista onde um recusado, por definição, não
    aparece. O mapa mandava o mantenedor a um lugar que não sabia responder."""
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=[]))

    html = _texto(_dentro().get("/escola/jornada/"))
    depois = html[html.index("Recusado") :]
    assert reverse("escola_recusados") in depois[: depois.index("Dentro da escola")]


# --------------------------------------- 5. aceitar de novo: as duas portas


def _volta_para_a_fila(id_da_linha="7"):
    return respx.post(FILA).mock(
        return_value=httpx.Response(
            200, json={"id": id_da_linha, "status": "aguardando"}
        )
    )


def _liberacao(resposta=None):
    return respx.post(f"{FILA}/7/decisao").mock(
        return_value=resposta
        or httpx.Response(200, json={"id": "7", "status": "ativa"})
    )


@respx.mock
def test_aceitar_de_novo_usa_as_duas_portas_que_ja_existem():
    """Nenhuma porta nova na `alunos`: o pedido volta para a fila e é liberado
    na sequência, o mesmo caminho de quem entra pelo site."""
    _recusados_respondem([_recusado()])
    volta = _volta_para_a_fila()
    libera = _liberacao()

    r = _dentro().post(GESTO, {"alvo": "7", "product_id": CURSO})

    assert volta.called and libera.called
    assert r.status_code == 302
    assert r["Location"].endswith("?resultado=reconsiderado")


@respx.mock
def test_os_dados_reenviados_sao_os_da_alunos_e_nao_os_do_formulario():
    """Reenviar o pedido REESCREVE nome, WhatsApp, turma e data da compra. Se o
    formulário pudesse ditá-los, este botão seria uma porta de edição silenciosa
    do cadastro de qualquer pessoa da fila."""
    _recusados_respondem(
        [
            _recusado(
                nome_completo="Ana Paula", whatsapp="(96) 99999-0000", turma="agosto"
            )
        ]
    )
    volta = _volta_para_a_fila()
    _liberacao()

    _dentro().post(
        GESTO,
        {
            "alvo": "7",
            "nome_completo": "Nome Trocado",
            "whatsapp": "(11) 90000-0000",
            "email": "outro@exemplo.com",
            "turma": "turma trocada",
            "product_id": CURSO,
        },
    )

    import json

    enviado = json.loads(volta.calls[0].request.content)
    assert enviado["nome_completo"] == "Ana Paula"
    assert enviado["whatsapp"] == "(96) 99999-0000"
    assert enviado["email"] == "ana@exemplo.com"
    assert enviado["turma"] == "agosto"


@respx.mock
def test_campo_vazio_nao_viaja_para_nao_apagar_o_que_a_pessoa_escreveu():
    """`turma: None` no corpo apagaria a turma da ficha. Apagar dado é o oposto
    do que este botão promete."""
    _recusados_respondem([_recusado(turma=None, comprou_em=None)])
    volta = _volta_para_a_fila()
    _liberacao()

    _dentro().post(GESTO, {"alvo": "7", "product_id": CURSO})

    import json

    enviado = json.loads(volta.calls[0].request.content)
    assert "turma" not in enviado
    assert "comprou_em" not in enviado


@respx.mock
def test_a_liberacao_que_falha_diz_onde_a_pessoa_ficou():
    """O pior desfecho é um clique a mais numa lista que ele já abre todo dia —
    nunca um "não deu certo" que o faria repetir o gesto aqui."""
    _recusados_respondem([_recusado()])
    _volta_para_a_fila()
    _liberacao(httpx.Response(500))

    r = _dentro().post(GESTO, {"alvo": "7", "product_id": CURSO})
    assert r["Location"].endswith("?resultado=reconsiderado-na-fila")

    html = _texto(_dentro().get(f"{TELA}?resultado=reconsiderado-na-fila"))
    assert "está esperando na fila" in html
    assert "Não repita aqui" in html


@respx.mock
def test_quem_ja_saiu_dos_recusados_recebe_recusa_honesta_e_nada_e_tentado():
    """Outra aba já aceitou, ou a própria pessoa reenviou o pedido. A porta de
    voltar à fila não é registrada aqui de propósito: se a view a chamasse,
    `respx` estouraria."""
    _recusados_respondem([_recusado(id="7")])
    r = _dentro().post(GESTO, {"alvo": "99", "product_id": CURSO})
    assert r["Location"].endswith("?resultado=reconsiderar-sumiu")


@respx.mock
def test_quem_ja_e_aluno_ou_foi_reembolsado_nao_volta_pela_fila():
    """O 409 da `alunos` tem DUAS causas (já tem matrícula que vale, ou foi
    reembolsado), e o recado nomeia as duas: escolher uma seria a tela afirmar
    o que não mediu."""
    _recusados_respondem([_recusado()])
    respx.post(FILA).mock(return_value=httpx.Response(409, json={"detail": "já tem"}))

    r = _dentro().post(GESTO, {"alvo": "7", "product_id": CURSO})
    assert r["Location"].endswith("?resultado=reconsiderar-nao-cabe")

    html = _texto(_dentro().get(f"{TELA}?resultado=reconsiderar-nao-cabe"))
    assert "já é aluna" in html
    assert "reembolsada" in html


@respx.mock
def test_sem_conseguir_ler_a_lista_nada_e_tentado_e_a_tela_avisa():
    """A porta de voltar à fila não está registrada: se a view tentasse aceitar
    alguém sem saber quem é, `respx` estouraria."""
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(500)
    )
    r = _dentro().post(GESTO, {"alvo": "7", "product_id": CURSO})
    assert r["Location"].endswith("?resultado=reconsiderar-nao-deu")


@respx.mock
def test_formulario_sem_alvo_nao_faz_nada_e_nao_grava_auditoria():
    """Nada foi tentado sobre pessoa nenhuma: uma linha aqui contaria uma ação
    que não existiu, no registro que alguém vai precisar ler um dia."""
    r = _dentro().post(GESTO, {})
    assert r.status_code == 302
    assert Registro.objects.count() == 0


def test_sem_sessao_o_gesto_vai_para_o_login():
    r = Client().post(GESTO, {"alvo": "7", "product_id": CURSO})
    assert r.status_code == 302
    assert r["Location"].startswith("/entrar/google?next=")


# ---------------------------------------------------------- 6. a auditoria


@respx.mock
def test_o_gesto_grava_uma_linha_com_verbo_proprio():
    """Verbo PRÓPRIO: "voltei atrás numa recusa" é a pergunta que os `liberar`
    não sabem responder, porque falam de gente que nunca foi recusada.

    UMA linha no caminho feliz, e não uma por salto: mesma disciplina do
    cadastro à mão, que também é um gesto de dois passos. O `detalhe` conta a
    viagem inteira."""
    _recusados_respondem([_recusado()])
    _volta_para_a_fila()
    _liberacao()

    _dentro().post(GESTO, {"alvo": "7", "product_id": CURSO})

    linha = Registro.objects.get()
    assert linha.acao == Registro.RECONSIDERAR
    assert linha.desfecho == Registro.OK
    assert linha.quem_email == DONO
    assert "liberada" in linha.detalhe


@respx.mock
def test_a_tentativa_que_falhou_tambem_deixa_linha():
    """Auditoria que só registra sucesso responde "quem aceitou?" e não responde
    "o que foi tentado aqui?" — e é a segunda pergunta que alguém faz quando um
    aluno diz "fui aceito e continuo sem acesso"."""
    _recusados_respondem([_recusado()])
    respx.post(FILA).mock(return_value=httpx.Response(409, json={"detail": "já tem"}))

    _dentro().post(GESTO, {"alvo": "7", "product_id": CURSO})

    linha = Registro.objects.get()
    assert linha.acao == Registro.RECONSIDERAR
    assert linha.desfecho == Registro.RECUSADO_PELA_CELULA
    assert linha.alvo == "7"


@respx.mock
def test_a_auditoria_nao_guarda_pii_de_quem_foi_aceito():
    """A regra da tabela: ela guarda o que o OPERADOR fez, nunca o dado da
    pessoa. Nome e telefone moram na `alunos`, que é quem decide quem os vê."""
    _recusados_respondem([_recusado()])
    _volta_para_a_fila()
    _liberacao()

    _dentro().post(GESTO, {"alvo": "7", "product_id": CURSO})

    for linha in Registro.objects.all():
        assert "Ana Paula" not in linha.detalhe
        assert "99999-0000" not in linha.detalhe
        assert "ana@exemplo.com" not in linha.detalhe


# ------------------------------------------------------------ 7. apagar de vez


def _apagar_de_vez(id_da_linha="7", resposta=None):
    return respx.delete(f"{FILA}/{id_da_linha}").mock(
        return_value=resposta or httpx.Response(200, json={"apagada": True})
    )


@respx.mock
def test_o_cartao_de_recusados_mostra_o_botao_apagar_de_vez():
    """O endereço aparece DENTRO do cartão, ao lado de "Aceitar mesmo assim" —
    não solto em outro lugar da página."""
    _recusados_respondem([_recusado()])
    html = _texto(_dentro().get(TELA))
    assert "Apagar de vez" in html
    assert reverse("escola_apagar_recusado") in html


@respx.mock
def test_apagar_de_vez_manda_DELETE_e_redireciona_para_apagado():
    apaga = _apagar_de_vez()

    r = _dentro().post(GESTO_APAGAR, {"alvo": "7"})

    assert apaga.called
    assert r.status_code == 302
    assert r["Location"].endswith("?resultado=apagado")


@respx.mock
def test_apagar_quem_ja_sumiu_dos_recusados_e_honesto_e_nada_muda():
    """A `alunos` diz 404 (a linha não é mais recusada, ou nunca foi): a tela
    não finge que apagou algo que já não estava lá."""
    _apagar_de_vez(resposta=httpx.Response(404))

    r = _dentro().post(GESTO_APAGAR, {"alvo": "7"})

    assert r["Location"].endswith("?resultado=apagar-sumiu")


@respx.mock
def test_apagar_quem_ainda_esta_aguardando_e_recusa_honesta():
    """409: a `alunos` recusa apagar quem ainda não foi decidido — a mesma
    fronteira que impede este botão de alcançar mais do que um recusado."""
    _apagar_de_vez(resposta=httpx.Response(409))

    r = _dentro().post(GESTO_APAGAR, {"alvo": "7"})

    assert r["Location"].endswith("?resultado=apagar-sumiu")


@respx.mock
def test_apagar_sem_resposta_diz_que_pode_ter_apagado_mesmo_assim():
    """O pior desfecho aqui é pior que o do `reconsiderar`: não há "a pessoa
    ficou esperando em tal lugar" para dizer, porque não sobra lugar nenhum se
    a exclusão chegou a acontecer do outro lado."""
    _apagar_de_vez(resposta=httpx.Response(500))

    r = _dentro().post(GESTO_APAGAR, {"alvo": "7"})

    assert r["Location"].endswith("?resultado=apagar-nao-deu")


@respx.mock
def test_apagar_sem_alvo_nao_faz_nada_e_nao_grava_auditoria():
    r = _dentro().post(GESTO_APAGAR, {})
    assert r.status_code == 302
    assert Registro.objects.count() == 0


def test_sem_sessao_o_gesto_de_apagar_vai_para_o_login():
    r = Client().post(GESTO_APAGAR, {"alvo": "7"})
    assert r.status_code == 302
    assert r["Location"].startswith("/entrar/google?next=")


@respx.mock
def test_fora_da_lista_de_administradores_nao_apaga():
    assert (
        _dentro("estranho@exemplo.com").post(GESTO_APAGAR, {"alvo": "7"}).status_code
        == 404
    )


@respx.mock
def test_o_gesto_de_apagar_recusa_GET():
    """Apagar por GET é apagar quando um pré-carregador de link, um antivírus
    corporativo ou um crawler autenticado abrir a página — e este é o único
    gesto desta área sem volta nenhuma."""
    assert _dentro().get(GESTO_APAGAR).status_code == 405


@respx.mock
def test_apagar_grava_uma_linha_com_verbo_proprio_e_nao_o_apagar_aposentado():
    apaga = _apagar_de_vez()

    _dentro().post(GESTO_APAGAR, {"alvo": "7"})

    linha = Registro.objects.get()
    assert linha.acao == Registro.APAGAR_RECUSADO
    assert linha.acao != Registro.APAGAR
    assert linha.desfecho == Registro.OK
    assert linha.quem_email == DONO
    assert linha.alvo == "7"
    assert apaga.called


@respx.mock
def test_apagar_falho_tambem_deixa_linha():
    """Auditoria que só registra sucesso não responde "o que foi tentado
    aqui?" — a mesma disciplina do `reconsiderar`."""
    _apagar_de_vez(resposta=httpx.Response(404))

    _dentro().post(GESTO_APAGAR, {"alvo": "7"})

    linha = Registro.objects.get()
    assert linha.acao == Registro.APAGAR_RECUSADO
    assert linha.desfecho == Registro.RECUSADO_PELA_CELULA
    assert linha.alvo == "7"
