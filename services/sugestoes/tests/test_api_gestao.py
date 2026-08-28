"""A superfície de gestão que o Admin consome (28/08/2026).

Lei: `docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`. A gestão das
ideias saiu das telas desta célula e passou a morar em `/admin/caixa/`; o Admin
pergunta e escreve por aqui, porque pela Lei 3 nenhuma célula lê o banco de
outra.

O que estes guardas protegem, em ordem de gravidade:

1. **A porta de máquina continua trancada** — todas as operações, não só a
   antiga, e a lista é DERIVADA da API para que rota nova nasça medida.
2. **O e-mail do aluno não atravessa a fronteira** — decisão do mantenedor no
   mesmo dia, mantendo a `DECISAO-EVO-01` §3.
3. **Nenhuma trava foi afrouxada na mudança de casa**: justificativa obrigatória,
   corredor do ChangeSpec e o portão do aprovador continuam recusando — agora
   pelo contrato, com a MESMA frase que a tela dizia.
4. **A plateia que atravessa é a mesma que o sininho avisa** ([INV-SUG13] cruzando
   a fronteira).
"""

import json

import pytest

from apps.core.avisos import interessados_em
from apps.sugestoes.models import Aviso, HistoricoStatus, Sugestao
from config.api import api

TOKEN = "token-do-par-admin-sugestoes"
IDEIAS = "/interno/gestao/ideias"
MANTENEDOR = "mantenedor@meshcraft.test"
# O id que atravessa a plataforma — o Admin o tem porque foi com ele que abriu a
# própria porta ([INV-SUG11]/[INV-SUG12]).
ID_DA_PLATAFORMA = "idt-do-mantenedor"


@pytest.fixture
def par_autorizado(settings):
    """O token do par, como o env real o forneceria (ver `test_sessao_interno`)."""
    settings.TOKENS_ACEITOS = {TOKEN}
    return TOKEN


def ler(client, por_email: str = ""):
    resposta = client.get(
        IDEIAS + (f"?por_email={por_email}" if por_email else ""),
        headers={"authorization": f"Bearer {TOKEN}"},
    )
    assert resposta.status_code == 200, resposta.content
    return resposta.json()


def escrever(client, caminho: str, corpo: dict):
    return client.post(
        caminho,
        data=json.dumps(corpo),
        content_type="application/json",
        headers={"authorization": f"Bearer {TOKEN}"},
    )


def uma(corpo, sugestao):
    return next(i for i in corpo["ideias"] if i["id"] == sugestao.id)


# ---------------------------------------------------------------------------
# 1. A porta de máquina — medida em TODAS as operações, derivadas da API
# ---------------------------------------------------------------------------


def operacoes_da_api():
    """Todo caminho+método publicado. Rota nova entra aqui sozinha."""
    return [
        (metodo, caminho)
        for caminho, item in api.get_openapi_schema()["paths"].items()
        for metodo in item
    ]


def test_ha_operacoes_para_medir():
    """Guarda que varre lista vazia é guarda verde à toa."""
    assert len(operacoes_da_api()) == 5


def test_nenhuma_operacao_responde_sem_o_token_do_par(client, db, par_autorizado):
    """A fronteira é do par, não da rota: uma rota nova nasce trancada.

    Sem esta varredura, a operação seguinte a ser acrescentada dependeria de
    alguém lembrar de escrever o guarda dela — e a que ninguém lembra é a que
    fica aberta.
    """
    for metodo, caminho in operacoes_da_api():
        endereco = caminho.replace("{sugestao_id}", "1")
        resposta = getattr(client, metodo)(endereco)
        assert resposta.status_code == 401, f"{metodo.upper()} {caminho} sem token"


# ---------------------------------------------------------------------------
# 2. O que atravessa a fronteira — e o que não atravessa
# ---------------------------------------------------------------------------


def test_o_email_do_aluno_nao_atravessa(client, db, par_autorizado, sugestao, plateia):
    """Decisão do mantenedor (28/08): o e-mail de quem sugeriu não sai da Caixa.

    A varredura é sobre o CORPO INTEIRO, em texto, e não sobre os campos que eu
    lembrei de conferir: um campo novo que carregue e-mail por descuido cai aqui
    sem ninguém ter previsto o nome dele.
    """
    plateia(sugestao, votantes=3, comentaristas=2, marca="fronteira")

    cru = json.dumps(ler(client))

    assert sugestao.autor.email not in cru
    assert "@exemplo.test" not in cru
    assert "@" not in cru, "algum e-mail atravessou a fronteira da Caixa"


def test_a_plateia_que_atravessa_e_a_que_o_sininho_avisa(
    client, db, par_autorizado, sugestao, plateia
):
    """[INV-SUG13] cruzando a fronteira: a promessa e a entrega são a mesma gente."""
    montada = plateia(sugestao, votantes=6, comentaristas=3, marca="cruza")
    Sugestao.objects.filter(pk=sugestao.pk).update(titulo=sugestao.titulo)
    assert montada  # cenário montado de verdade

    do_contrato = uma(ler(client), sugestao)["pessoas"]

    assert do_contrato == len(interessados_em(sugestao))


def test_os_fatos_da_ideia_atravessam_inteiros(
    client, db, par_autorizado, caixa, sugestao, equipe
):
    """Votos, comentários, estado e as duas perguntas do corredor."""
    caixa.votar(sugestao)
    corpo = uma(ler(client), sugestao)

    assert corpo["titulo"] == sugestao.titulo
    assert corpo["votos"] == 1
    assert corpo["status"] == Sugestao.Status.EM_ANALISE
    assert corpo["tem_avaliacao"] is False
    assert corpo["tem_changespec"] is False
    assert corpo["ja_ouviram"] is False
    assert corpo["avaliacao"] is None


def test_quem_nao_esta_na_lista_de_aprovadores_ve_pode_assinar_falso(
    client, db, par_autorizado, sugestao, lista_de_aprovadores
):
    lista_de_aprovadores(MANTENEDOR)

    assert ler(client, por_email="outra.pessoa@meshcraft.test")["pode_assinar"] is False
    assert ler(client, por_email=MANTENEDOR)["pode_assinar"] is True


# ---------------------------------------------------------------------------
# 3. Nenhuma trava afrouxou na mudança de casa
# ---------------------------------------------------------------------------


def test_mudar_de_fase_grava_historico_e_avisa_a_plateia(
    client, db, par_autorizado, sugestao, plateia
):
    """A escrita passa pelo caminho de sempre — não por uma porta nova."""
    plateia(sugestao, votantes=4, marca="avisa")

    resposta = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/status",
        {
            "por_email": MANTENEDOR,
            "por_id_da_plataforma": ID_DA_PLATAFORMA,
            "status": "planejado",
            "nota": "vai entrar",
        },
    )

    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["status"] == "planejado"
    assert HistoricoStatus.objects.filter(sugestao=sugestao).count() == 1
    assert Aviso.objects.filter(sugestao=sugestao).count() == 5


def test_nao_planejado_sem_justificativa_e_recusado(
    client, db, par_autorizado, sugestao
):
    """A regra da spec §10 continua mordendo, agora pelo contrato."""
    resposta = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/status",
        {
            "por_email": MANTENEDOR,
            "por_id_da_plataforma": ID_DA_PLATAFORMA,
            "status": "nao_planejado",
            "nota": "",
        },
    )

    assert resposta.status_code == 422
    assert "escreva o porquê" in resposta.json()["erro"]
    assert Sugestao.objects.get(pk=sugestao.pk).status == Sugestao.Status.EM_ANALISE


def test_o_corredor_do_changespec_continua_barrando(
    client, db, par_autorizado, caixa, sugestao
):
    """[INV-SUG10] pelo contrato: sem assinatura, não vira obra."""
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="vai")

    resposta = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/status",
        {
            "por_email": MANTENEDOR,
            "por_id_da_plataforma": ID_DA_PLATAFORMA,
            "status": "em_desenvolvimento",
            "nota": "começou",
        },
    )

    assert resposta.status_code == 422
    assert "ChangeSpec" in resposta.json()["erro"]
    assert Sugestao.objects.get(pk=sugestao.pk).status == Sugestao.Status.PLANEJADO


def test_estar_no_admin_nao_da_o_direito_de_assinar(
    client, db, par_autorizado, sugestao, lista_de_aprovadores
):
    """O SEGUNDO portão não mudou de dono, e esta é a prova.

    Quem chega aqui já passou pela porta do Admin — o token do par é justamente
    a afirmação disso. Ainda assim a assinatura é recusada: moderar e autorizar
    obra continuam sendo papéis diferentes (decisão do mantenedor em 25/08).
    """
    lista_de_aprovadores(MANTENEDOR)

    resposta = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/changespec",
        {
            "por_email": "outra.pessoa@meshcraft.test",
            "por_id_da_plataforma": "idt-de-outra-pessoa",
            "change_id": "CS-SUGESTOES-0001",
            "documento": "docs/changespecs/CS-SUGESTOES-0001.md",
            "aprovado_por": "Alguém",
            "aprovado_em": "2026-08-28",
        },
    )

    assert resposta.status_code == 403
    assert sugestao.changespecs.count() == 0


def test_a_lista_de_aprovadores_vazia_recusa_todo_mundo(
    client, db, par_autorizado, sugestao
):
    """Fail-closed: a ausência da lista não vira 'então pode qualquer um'."""
    resposta = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/changespec",
        {
            "por_email": MANTENEDOR,
            "por_id_da_plataforma": ID_DA_PLATAFORMA,
            "change_id": "CS-SUGESTOES-0001",
            "documento": "docs/changespecs/CS-SUGESTOES-0001.md",
            "aprovado_por": "Davi",
            "aprovado_em": "2026-08-28",
        },
    )

    assert resposta.status_code == 403


def test_quem_aprova_registra_e_o_corredor_abre(
    client, db, par_autorizado, caixa, sugestao, lista_de_aprovadores
):
    lista_de_aprovadores(MANTENEDOR)
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="vai")

    registro = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/changespec",
        {
            "por_email": MANTENEDOR,
            "por_id_da_plataforma": ID_DA_PLATAFORMA,
            "change_id": "CS-SUGESTOES-0001",
            "documento": "docs/changespecs/CS-SUGESTOES-0001.md",
            "aprovado_por": "Davi (mantenedor)",
            "aprovado_em": "2026-08-28",
        },
    )
    assert registro.status_code == 200, registro.content
    assert registro.json()["tem_changespec"] is True

    andou = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/status",
        {
            "por_email": MANTENEDOR,
            "por_id_da_plataforma": ID_DA_PLATAFORMA,
            "status": "em_desenvolvimento",
            "nota": "começou",
        },
    )

    assert andou.status_code == 200, andou.content
    assert andou.json()["status"] == "em_desenvolvimento"


def test_avaliar_pelo_contrato_escreve_a_decisao_de_produto(
    client, db, par_autorizado, sugestao
):
    resposta = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/avaliacao",
        {
            "por_email": MANTENEDOR,
            "por_id_da_plataforma": ID_DA_PLATAFORMA,
            "impacto_educacional": 4,
            "impacto_comercial": 5,
            "esforco_tecnico": 3,
            "notas": "cabe no trimestre",
            "decisao_produto": "Página pública com modelo fixo.",
        },
    )

    assert resposta.status_code == 200, resposta.content
    corpo = resposta.json()
    assert corpo["tem_avaliacao"] is True
    assert corpo["avaliacao"]["decisao_produto"] == "Página pública com modelo fixo."
    assert corpo["avaliacao"]["impacto_comercial"] == 5


def test_uma_fase_que_a_equipe_nao_escolhe_e_recusada(
    client, db, par_autorizado, sugestao
):
    """`mesclado` não está no leque da equipe (é operação transacional, V1.1)."""
    resposta = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/status",
        {
            "por_email": MANTENEDOR,
            "por_id_da_plataforma": ID_DA_PLATAFORMA,
            "status": "mesclado",
            "nota": "juntada",
        },
    )

    assert resposta.status_code == 422


def test_moderar_sem_o_id_da_plataforma_recusa_com_instrucao(
    client, db, par_autorizado, sugestao
):
    """[INV-SUG12] O fato não se afirma sem quem o afirmou — e a recusa ensina.

    Sem esta tradução, a mesma situação chegaria ao Admin como erro 500: um
    "deu errado" sem caminho, para um problema cuja solução é a pessoa entrar
    uma vez no site.
    """
    resposta = escrever(
        client,
        f"{IDEIAS}/{sugestao.id}/status",
        {"por_email": MANTENEDOR, "status": "planejado", "nota": "vai"},
    )

    assert resposta.status_code == 422
    assert "entre uma vez em meshcraft.top" in resposta.json()["erro"].lower()
    assert Sugestao.objects.get(pk=sugestao.pk).status == Sugestao.Status.EM_ANALISE


# ---------------------------------------------------------------------------
# 4. Os números de GENTE — a conta que só esta célula consegue fazer
# ---------------------------------------------------------------------------


def test_quem_esta_atras_de_duas_ideias_conta_uma_vez_so(
    client, db, par_autorizado, caixa, dentro, sugestao
):
    """É por isto que estes três números viajam prontos.

    O consumidor tem a contagem POR IDEIA; somá-las contaria duas vezes quem
    está atrás de duas. A dedução por pessoa só existe deste lado da fronteira,
    onde as plateias são conjuntos e não números.
    """
    outra = caixa.publicar("Outra ideia")
    caixa.votar(outra)
    caixa.votar(sugestao)

    corpo = ler(client)
    soma_das_plateias = sum(i["pessoas"] for i in corpo["ideias"])

    assert corpo["pessoas_esperando"] < soma_das_plateias, (
        "a mesma pessoa está atrás das duas ideias e teria sido contada duas "
        "vezes numa soma ingênua"
    )


def test_ideia_ja_respondida_nao_deixa_ninguem_esperando(
    client, db, par_autorizado, caixa, sugestao
):
    """Recusar com explicação é responder — e a conta para de cobrar."""
    assert ler(client)["pessoas_esperando"] == 1

    caixa.mudar_status(
        sugestao, Sugestao.Status.NAO_PLANEJADO, nota="o material é licenciado"
    )

    assert ler(client)["pessoas_esperando"] == 0
    assert ler(client)["silencio_medio_em_dias"] is None


def test_o_silencio_longo_e_contado_a_parte(client, db, par_autorizado, sugestao):
    """Um mês sem notícia deixa de ser fila e vira abandono — e o número diz."""
    from datetime import timedelta

    from django.utils import timezone

    assert ler(client)["pessoas_em_silencio_demais"] == 0

    Sugestao.objects.filter(pk=sugestao.pk).update(
        criado_em=timezone.now() - timedelta(days=45)
    )

    corpo = ler(client)
    assert corpo["pessoas_em_silencio_demais"] == 1
    assert corpo["silencio_medio_em_dias"] == 45
