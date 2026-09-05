"""Guardas da porta de leitura (`/api/metricas`) — o degrau 7.4.

Por que ela precisa de guarda próprio, e forte: uma porta de máquina é a
superfície mais fácil de estragar do sistema, porque ninguém olha para ela. Não
tem tela, não tem link, não aparece no navegador de ninguém. Uma operação nova
sem cadeado fica verde, e um campo a mais num Schema não quebra página nenhuma.

AS SETE COISAS QUE ESTE ARQUIVO PROVA
-------------------------------------
1. **Fechada por padrão.** Sem token, com token errado ou com o env ausente é
   401 em TODA operação, e a lista de operações é MEDIDA do schema vivo, nunca
   digitada. Operação nova sem cadeado reprova sozinha.
2. **A sonda continua aberta.** `/healthz` responde sem token: o healthcheck do
   compose não tem crachá, e uma porta que o fechasse derrubaria a célula no
   deploy, com o erro aparecendo longe da causa.
3. **O dia é o de São Paulo.** Um fato das 22h30 do dia 30 conta no dia 30, e
   não no dia 1 do mês seguinte. É a conta que decide em que mês uma pessoa
   entrou, e é a mesma que o placar faz do outro lado (`armadilhas/099`).
4. **A fronteira de site fecha (Lei 9).** Fato de outro site não entra em
   contagem nem em cobertura, nem por engano nem por soma.
5. **Ausência não vira zero.** Dia sem fato não aparece na contagem, e assunto
   que nunca chegou não aparece na cobertura. É a diferença entre "medi e deu
   zero" e "não medi", e é a lei desta célula.
6. **A contagem de conquistas não oferece total geral.** `pessoa` e `matricula`
   são vocabulários de identidade diferentes, e a resposta não tem nenhum campo
   que os atravesse. Somar maçãs com laranjas passa a exigir uma decisão de quem
   consome, em vez de acontecer por acidente (`armadilhas/303`).
7. **Sujeito sem conquista é 200 com lista vazia, nunca 404.** Esta célula não
   conhece cadastro nenhum: ela sabe o que os fatos trouxeram, e "não tenho
   marco para este id" não é o mesmo que "este sujeito não existe".

O CENÁRIO TEM DENTE, DE PROPÓSITO
---------------------------------
Ele inclui um fato de OUTRO site, um fato de outro assunto, um dia vazio no
meio do intervalo e um evento morto. Um cenário só com o caso feliz passaria
mesmo se o filtro de site não existisse, se a contagem ignorasse o `tipo` e se
a fila de mortos devolvesse o corpo cru para todo mundo.

No cenário de marcos o dente é o mesmo id em DOIS vocabulários: `sujeito-1`
existe como pessoa e como matrícula, com conquistas diferentes. Um cenário sem
essa colisão passaria mesmo se a porta ignorasse o `sujeito_tipo` por inteiro,
que é exatamente a mistura que o contrato proíbe.
"""

from __future__ import annotations

import datetime as dt
import uuid
from zoneinfo import ZoneInfo

import pytest
from django.test import Client

from apps.fatos.models import Evento, EventoMorto, Marco

pytestmark = pytest.mark.django_db

BASE = "/api/metricas"
TOKEN = "token-do-par-admin"
SITE = "site-da-escola"
OUTRO_SITE = "site-de-outra-escola"
SP = ZoneInfo("America/Sao_Paulo")

CADASTRO = "identidade.pessoa-cadastrada"
QUIZ = "quiz.completado"


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def pedir(caminho: str, token: str | None = TOKEN):
    cabecalhos = {}
    if token:
        cabecalhos["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return Client().get(f"{BASE}{caminho}", **cabecalhos)


def gravar(tipo: str, quando: dt.datetime, site: str = SITE) -> Evento:
    return Evento.objects.create(
        event_id=uuid.uuid4(),
        tipo=tipo,
        versao=1,
        site_id=site,
        ocorrido_em=quando,
        dados={"site_id": site},
    )


def operacoes_da_porta() -> list[tuple[str, str]]:
    """Toda operação do schema VIVO, com os parâmetros de caminho preenchidos.

    Medida, e não digitada: é isto que faz o guarda de 401 alcançar a operação
    que alguém acrescentar amanhã sem ler este arquivo.

    O import mora aqui dentro, e não no topo, porque esta função roda na COLETA
    do pytest: importar a API no topo do módulo a construiria antes de o
    pytest-django terminar de configurar o Django.

    A medição é do schema VIVO porque o contrato congelado ainda não existe: ele
    nasce pelo `RITOS.md` §3, e a ordem porta-antes-de-contrato é obrigatória
    (`armadilhas/228`). Quando ele existir, esta função passa a ler o congelado,
    porque é contra a PROMESSA que o cadeado precisa valer.
    """
    from config.api import api

    schema = api.get_openapi_schema(path_prefix="")
    return [
        (metodo, caminho.replace("{morto_id}", "1"))
        for caminho, item in schema["paths"].items()
        for metodo in item
    ]


# ---------------------------------------------------------------------------
# 1. Fechada por padrão
# ---------------------------------------------------------------------------


def test_o_schema_vivo_tem_as_seis_operacoes():
    """Se este número mudar, o teste de 401 abaixo mudou de escopo junto."""
    assert len(operacoes_da_porta()) == 6


@pytest.mark.parametrize("metodo,caminho", operacoes_da_porta())
def test_toda_operacao_recusa_sem_token(metodo, caminho):
    resposta = Client().generic(metodo.upper(), f"{BASE}{caminho}")
    assert resposta.status_code == 401, f"{metodo} {caminho} respondeu sem token"


@pytest.mark.parametrize("metodo,caminho", operacoes_da_porta())
def test_toda_operacao_recusa_token_errado(metodo, caminho):
    resposta = Client().generic(
        metodo.upper(),
        f"{BASE}{caminho}",
        HTTP_AUTHORIZATION="Bearer token-de-quem-nao-e-da-casa",
    )
    assert resposta.status_code == 401, f"{metodo} {caminho} aceitou token errado"


def test_env_ausente_fecha_a_porta_para_todo_mundo(settings):
    """Sem `TOKENS_ACEITOS_*` no env, o conjunto nasce vazio e ninguém entra.

    É o modo de falha que importa: a célula sobe antes de o token existir, e uma
    porta que se abrisse "porque não há lista" ficaria aberta justamente na
    janela em que ninguém está olhando.
    """
    settings.TOKENS_ACEITOS = set()
    assert pedir(f"/cobertura?site_id={SITE}").status_code == 401


def test_a_sonda_continua_aberta():
    """O healthcheck do compose não tem crachá, e não pode passar a precisar de um."""
    assert Client().get("/healthz").status_code == 200


# ---------------------------------------------------------------------------
# 2. Contagens
# ---------------------------------------------------------------------------


def test_conta_por_dia_so_o_assunto_e_o_site_pedidos():
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 11, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 4, 9, 0, tzinfo=SP))
    gravar(QUIZ, dt.datetime(2026, 9, 2, 12, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 13, 0, tzinfo=SP), site=OUTRO_SITE)

    corpo = pedir(
        f"/contagens?site_id={SITE}&tipo={CADASTRO}&de=2026-09-01&ate=2026-09-30"
    ).json()

    assert corpo["total"] == 3
    assert corpo["por_dia"] == [
        {"dia": "2026-09-02", "quantidade": 2},
        {"dia": "2026-09-04", "quantidade": 1},
    ], "o dia 3, sem fato, não pode aparecer como zero"


def test_sem_tipo_conta_todos_os_assuntos_do_site():
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP))
    gravar(QUIZ, dt.datetime(2026, 9, 2, 12, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 2, 13, 0, tzinfo=SP), site=OUTRO_SITE)

    corpo = pedir(f"/contagens?site_id={SITE}&de=2026-09-01&ate=2026-09-30").json()

    assert corpo["total"] == 2


def test_o_dia_e_o_de_sao_paulo_e_nao_o_de_utc():
    """22h30 do dia 30 em São Paulo é 01h30 do dia 1 em UTC.

    Com o fuso errado esta pessoa cairia no mês seguinte, sem erro em lugar
    nenhum, e a meta do mantenedor mediria outra coisa (`armadilhas/099`).
    """
    gravar(CADASTRO, dt.datetime(2026, 9, 30, 22, 30, tzinfo=SP))

    setembro = pedir(f"/contagens?site_id={SITE}&de=2026-09-01&ate=2026-09-30").json()
    outubro = pedir(f"/contagens?site_id={SITE}&de=2026-10-01&ate=2026-10-31").json()

    assert setembro["total"] == 1
    assert outubro["total"] == 0


def test_intervalo_invertido_e_recusado():
    resposta = pedir(f"/contagens?site_id={SITE}&de=2026-09-30&ate=2026-09-01")
    assert resposta.status_code == 422
    assert "invertido" in resposta.json()["detail"]


def test_intervalo_maior_que_o_teto_e_recusado():
    resposta = pedir(f"/contagens?site_id={SITE}&de=2020-01-01&ate=2026-09-30")
    assert resposta.status_code == 422
    assert "pedaços" in resposta.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Cobertura
# ---------------------------------------------------------------------------


def test_cobertura_diz_de_cada_assunto_quantos_e_quando_foi_o_ultimo():
    gravar(CADASTRO, dt.datetime(2026, 9, 1, 10, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 3, 10, 0, tzinfo=SP))
    gravar(QUIZ, dt.datetime(2026, 9, 2, 10, 0, tzinfo=SP))
    gravar(CADASTRO, dt.datetime(2026, 9, 4, 10, 0, tzinfo=SP), site=OUTRO_SITE)

    corpo = pedir(f"/cobertura?site_id={SITE}").json()
    por_tipo = {linha["tipo"]: linha for linha in corpo["tipos"]}

    assert set(por_tipo) == {CADASTRO, QUIZ}, "assunto de outro site vazou"
    assert por_tipo[CADASTRO]["quantidade"] == 2
    assert por_tipo[CADASTRO]["celula"] == "identidade"
    assert por_tipo[CADASTRO]["ultimo_ocorrido_em"].startswith("2026-09-03")


def test_assunto_que_nunca_chegou_nao_aparece_como_zero():
    """A ausência é a resposta, e quem compara com o esperado é a `admin`."""
    gravar(CADASTRO, dt.datetime(2026, 9, 1, 10, 0, tzinfo=SP))

    corpo = pedir(f"/cobertura?site_id={SITE}").json()

    assert [linha["tipo"] for linha in corpo["tipos"]] == [CADASTRO]


# ---------------------------------------------------------------------------
# 4. A fila de eventos mortos
# ---------------------------------------------------------------------------


def morto(motivo: str = "o corpo não é JSON válido") -> EventoMorto:
    return EventoMorto.objects.create(
        corpo='{"event": "quiz.completado", quebrado',
        motivo=motivo,
        tipo_declarado="quiz.completado",
    )


def test_a_lista_de_mortos_nao_carrega_o_corpo_cru():
    """O corpo pode conter o que esta casa não guarda; em lote, seria espalhar."""
    morto()

    corpo = pedir("/eventos-mortos").json()

    assert corpo["total"] == 1
    assert "corpo" not in corpo["itens"][0]
    assert corpo["itens"][0]["motivo"].startswith("o corpo não é JSON")


def test_inspecionar_um_morto_traz_o_corpo():
    alvo = morto()

    corpo = pedir(f"/eventos-mortos/{alvo.id}").json()

    assert corpo["corpo"] == '{"event": "quiz.completado", quebrado'


def test_morto_que_nao_existe_e_404_e_nao_resposta_vazia():
    assert pedir("/eventos-mortos/4242").status_code == 404


def test_o_cursor_anda_do_mais_novo_para_o_mais_velho_sem_repetir():
    primeiro, segundo, terceiro = morto(), morto(), morto()

    pagina1 = pedir("/eventos-mortos?limite=2").json()
    pagina2 = pedir(f"/eventos-mortos?limite=2&apos={pagina1['proximo_cursor']}").json()

    assert [item["id"] for item in pagina1["itens"]] == [terceiro.id, segundo.id]
    assert [item["id"] for item in pagina2["itens"]] == [primeiro.id]
    assert pagina2["proximo_cursor"] is None
    assert pagina1["total"] == 3, "o total conta a fila inteira, não a página"


def test_estado_desconhecido_e_recusado_dizendo_quais_existem():
    resposta = pedir("/eventos-mortos?estado=resolvido")

    assert resposta.status_code == 422
    assert "descartado" in resposta.json()["detail"]


def test_limite_fora_da_faixa_e_recusado():
    assert pedir("/eventos-mortos?limite=0").status_code == 422
    assert pedir("/eventos-mortos?limite=201").status_code == 422


# ---------------------------------------------------------------------------
# 5. As conquistas (marcos)
# ---------------------------------------------------------------------------

#: O mesmo texto de id em dois vocabulários de identidade. É o dente do cenário
#: de marcos: com ele, uma porta que ignorasse `sujeito_tipo` some as duas
#: listas e nenhum caso feliz percebe.
ID_REPETIDO = "sujeito-1"


def marcar(sujeito_tipo: str, sujeito_id: str, tipo: str, dia: dt.date) -> Marco:
    return Marco.objects.create(
        sujeito_tipo=sujeito_tipo,
        sujeito_id=sujeito_id,
        tipo=tipo,
        dia=dia,
        event_id=uuid.uuid4(),
    )


def cenario_de_conquistas() -> None:
    """Dois vocabulários, três tipos, um dia vazio no meio e um fora da janela."""
    marcar(Marco.Sujeito.PESSOA, "p-1", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 9, 2))
    marcar(Marco.Sujeito.PESSOA, "p-2", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 9, 2))
    marcar(Marco.Sujeito.PESSOA, "p-3", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 9, 4))
    marcar(
        Marco.Sujeito.PESSOA, "p-1", Marco.Tipo.ESCREVEU_NO_FORUM, dt.date(2026, 9, 4)
    )
    marcar(
        Marco.Sujeito.MATRICULA,
        "mat-1",
        Marco.Tipo.VIROU_ALUNO_COMPRANDO,
        dt.date(2026, 9, 2),
    )
    marcar(
        Marco.Sujeito.PESSOA, "p-9", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 10, 20)
    )


def test_conta_as_conquistas_por_dia_dentro_de_cada_vocabulario():
    """Cada linha diz em que vocabulário foi contada, e o dia vazio não vira zero."""
    cenario_de_conquistas()

    corpo = pedir("/marcos/contagens?de=2026-09-01&ate=2026-09-30").json()
    por_linha = {
        (linha["sujeito_tipo"], linha["tipo"]): linha for linha in corpo["conquistas"]
    }

    assert set(por_linha) == {
        ("pessoa", "entrou-no-site"),
        ("pessoa", "escreveu-no-forum"),
        ("matricula", "virou-aluno-comprando"),
    }, "a conquista de outubro entrou numa janela de setembro"
    entrou = por_linha[("pessoa", "entrou-no-site")]
    assert entrou["total"] == 3
    assert entrou["por_dia"] == [
        {"dia": "2026-09-02", "quantidade": 2},
        {"dia": "2026-09-04", "quantidade": 1},
    ], "o dia 3, sem conquista, não pode aparecer como zero"


def test_a_contagem_nao_junta_o_mesmo_tipo_de_dois_vocabularios():
    """Duas linhas, e nunca uma só, quando o mesmo tipo existe nos dois lados.

    Nada na tabela impede isso: a chave única é (sujeito, id, tipo), e o dia em
    que uma derivação creditar a mesma conquista à pessoa E à matrícula, uma
    contagem agrupada só por `tipo` diria "2" onde a verdade são dois números de
    coisas diferentes. O guarda existe porque essa fusão não deixa erro nenhum
    para trás: o total fecha, e é o vocabulário que se perde.
    """
    marcar(
        Marco.Sujeito.PESSOA,
        "p-1",
        Marco.Tipo.VIROU_ALUNO_COMPRANDO,
        dt.date(2026, 9, 2),
    )
    marcar(
        Marco.Sujeito.MATRICULA,
        "mat-1",
        Marco.Tipo.VIROU_ALUNO_COMPRANDO,
        dt.date(2026, 9, 2),
    )

    corpo = pedir("/marcos/contagens?de=2026-09-01&ate=2026-09-30").json()

    assert sorted(linha["sujeito_tipo"] for linha in corpo["conquistas"]) == [
        "matricula",
        "pessoa",
    ], "os dois vocabulários caíram na mesma linha"
    assert [linha["total"] for linha in corpo["conquistas"]] == [1, 1]


def test_a_contagem_de_conquistas_nao_oferece_total_geral():
    """A ausência é o desenho: somar `pessoa` com `matricula` seria maçã com laranja.

    O guarda olha o CORPO inteiro, e não um campo nomeado, porque a forma de
    esta lei morrer é alguém acrescentar um `total` "por conveniência da tela" e
    ninguém reparar: quem consome somaria dois vocabulários de identidade sem
    nunca decidir somá-los (`armadilhas/303`).
    """
    cenario_de_conquistas()

    corpo = pedir("/marcos/contagens?de=2026-09-01&ate=2026-09-30").json()

    assert set(corpo) == {
        "sujeito_tipo",
        "tipo",
        "de",
        "ate",
        "conquistas",
    }, "a resposta ganhou um campo que atravessa os dois vocabulários"


def test_a_contagem_de_conquistas_filtra_por_vocabulario_e_por_tipo():
    cenario_de_conquistas()

    so_matricula = pedir(
        "/marcos/contagens?de=2026-09-01&ate=2026-09-30&sujeito_tipo=matricula"
    ).json()
    so_forum = pedir(
        "/marcos/contagens?de=2026-09-01&ate=2026-09-30&tipo=escreveu-no-forum"
    ).json()

    assert [linha["tipo"] for linha in so_matricula["conquistas"]] == [
        "virou-aluno-comprando"
    ]
    assert [linha["sujeito_tipo"] for linha in so_forum["conquistas"]] == ["pessoa"]


def test_a_contagem_de_conquistas_recusa_intervalo_invertido():
    resposta = pedir("/marcos/contagens?de=2026-09-30&ate=2026-09-01")

    assert resposta.status_code == 422
    assert "invertido" in resposta.json()["detail"]


def test_a_contagem_de_conquistas_recusa_janela_acima_do_teto():
    resposta = pedir("/marcos/contagens?de=2020-01-01&ate=2026-09-30")

    assert resposta.status_code == 422
    assert "pedaços" in resposta.json()["detail"]


def test_a_contagem_de_conquistas_recusa_vocabulario_desconhecido():
    """Vocabulário que não existe é recusa, e a recusa diz quais existem."""
    resposta = pedir(
        "/marcos/contagens?de=2026-09-01&ate=2026-09-30&sujeito_tipo=aluno"
    )

    assert resposta.status_code == 422
    assert "matricula" in resposta.json()["detail"]


def test_a_contagem_de_conquistas_recusa_conquista_desconhecida():
    resposta = pedir("/marcos/contagens?de=2026-09-01&ate=2026-09-30&tipo=virou-rico")

    assert resposta.status_code == 422
    assert "entrou-no-site" in resposta.json()["detail"]


def test_os_marcos_de_um_sujeito_vem_do_mais_antigo_para_o_mais_novo():
    """Com a linhagem junto: o `event_id` é o que permite conferir até o começo."""
    primeiro = marcar(
        Marco.Sujeito.PESSOA, "p-1", Marco.Tipo.ENTROU_NO_SITE, dt.date(2026, 9, 2)
    )
    depois = marcar(
        Marco.Sujeito.PESSOA, "p-1", Marco.Tipo.ESCREVEU_NO_FORUM, dt.date(2026, 9, 9)
    )

    corpo = pedir("/marcos?sujeito_tipo=pessoa&sujeito_id=p-1").json()

    assert [marco["tipo"] for marco in corpo["marcos"]] == [
        "entrou-no-site",
        "escreveu-no-forum",
    ]
    assert corpo["marcos"][0]["event_id"] == str(primeiro.event_id)
    assert corpo["marcos"][1]["event_id"] == str(depois.event_id)
    assert corpo["marcos"][0]["procedencia"] == "automatico"


def test_a_lista_de_marcos_nao_mistura_os_dois_vocabularios():
    """O mesmo id em dois vocabulários são dois sujeitos, e nunca se encontram."""
    marcar(
        Marco.Sujeito.PESSOA,
        ID_REPETIDO,
        Marco.Tipo.ENTROU_NO_SITE,
        dt.date(2026, 9, 2),
    )
    marcar(
        Marco.Sujeito.MATRICULA,
        ID_REPETIDO,
        Marco.Tipo.VIROU_ALUNO_COMPRANDO,
        dt.date(2026, 9, 3),
    )

    pessoa = pedir(f"/marcos?sujeito_tipo=pessoa&sujeito_id={ID_REPETIDO}").json()
    matricula = pedir(f"/marcos?sujeito_tipo=matricula&sujeito_id={ID_REPETIDO}").json()

    assert [marco["tipo"] for marco in pessoa["marcos"]] == ["entrou-no-site"]
    assert [marco["tipo"] for marco in matricula["marcos"]] == ["virou-aluno-comprando"]


def test_sujeito_sem_conquista_e_200_com_lista_vazia_e_nunca_404():
    """Esta célula não conhece cadastro: 404 afirmaria que o sujeito não existe."""
    resposta = pedir("/marcos?sujeito_tipo=pessoa&sujeito_id=nunca-fez-nada")

    assert resposta.status_code == 200
    assert resposta.json()["marcos"] == []


def test_a_lista_de_marcos_recusa_vocabulario_desconhecido():
    resposta = pedir("/marcos?sujeito_tipo=aluno&sujeito_id=p-1")

    assert resposta.status_code == 422
    assert "pessoa" in resposta.json()["detail"]


def test_a_lista_de_marcos_exige_as_duas_partes_do_sujeito():
    """Id sozinho é ambíguo, e ambiguidade aqui vira contagem errada de gente."""
    assert pedir("/marcos?sujeito_id=p-1").status_code == 422
    assert pedir("/marcos?sujeito_tipo=pessoa").status_code == 422
