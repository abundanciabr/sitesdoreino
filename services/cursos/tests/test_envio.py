"""O checkpoint, do lado de quem entrega: `envio.entregar` e a tela da aula.

O que este arquivo protege, e por que cada coisa:

1. **Entregar exige a porta em produção ou devolvida e TODAS as pausas
   registradas** ([INV-CUR-P3]): a recusa vem com a frase, e nada fica gravado.
2. **Entregar grava o `Envio` 1, muda a porta para `enviada` e enfileira o
   `envio.recebido.v1`** com o `data` do contrato, na mesma transação.
3. **O reenvio só nasce de `devolvida`, e leva o número 2**: cada volta é um
   envio novo, e o anterior fica como história.
4. **Os links, o README e a autoavaliação são validados** com frase para gente:
   URL http(s) e rótulo em cada link, o do arquivo presente, prévia sem link
   pulada; com instrumento, uma nota dentro da escala e uma frase por critério
   (e a versão do instrumento gravada, P04); sem instrumento, texto livre.
5. **A tela**: o formulário aparece fechado (com o porquê) e aberto nos estados
   certos; entregar pela tela grava e a aula passa a dizer "recebido em,
   revisão até" sem formulário; a recusa volta para o checkpoint com a frase;
   `devolvida` reabre como reenvio; o estouro registrado aparece; a hora é a
   de São Paulo; e nenhuma resposta reescreve o cookie do site
   (`armadilhas/143`).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cursos import envio as checkpoint
from apps.cursos.models import (
    Envio,
    Instrumento,
    OutboxEvent,
    Progresso,
    RegistroDePausa,
)
from tests.conftest import ARQUIVO, AUTOAVALIACAO, COOKIE, README, entrega

pytestmark = pytest.mark.django_db

SOLIDO = "https://previas.exemplo.test/ana/solido.png"

# O que o navegador manda quando a pessoa preenche o formulário inteiro: o
# arquivo, uma prévia com link e uma sem, o README e a autoavaliação livre.
FORMULARIO = {
    "arquivo": ARQUIVO,
    "previa_rotulo_0": "Sólido",
    "previa_url_0": SOLIDO,
    "previa_rotulo_1": "Wireframe",
    "previa_url_1": "",
    "readme": README,
    "autoavaliacao": AUTOAVALIACAO,
}


# ------------------------------------------------ 1. quem pode entregar
def test_entregar_exige_todas_as_pausas_registradas(ana_pronta):
    RegistroDePausa.objects.filter(pessoa=ana_pronta.pessoa).first().delete()
    with pytest.raises(checkpoint.EnvioRecusado, match="fechado até todas as pausas"):
        checkpoint.entregar(ana_pronta, **entrega())
    assert Envio.objects.count() == 0
    assert OutboxEvent.objects.count() == 0
    assert (
        Progresso.objects.get(pk=ana_pronta.pk).estado == Progresso.Estado.EM_PRODUCAO
    )


@pytest.mark.parametrize(
    "estado",
    [
        Progresso.Estado.TRANCADA,
        Progresso.Estado.DISPONIVEL,
        Progresso.Estado.ENVIADA,
        Progresso.Estado.CONCLUIDA,
    ],
)
def test_entregar_so_com_a_porta_em_producao_ou_devolvida(ana_pronta, estado):
    ana_pronta.estado = estado
    if estado == Progresso.Estado.CONCLUIDA:
        ana_pronta.concluida_em = timezone.now()
    ana_pronta.save()
    with pytest.raises(checkpoint.EnvioRecusado) as recusa:
        checkpoint.entregar(ana_pronta, **entrega())
    assert str(recusa.value) == checkpoint.POR_QUE_NAO_ENTREGA[estado]
    assert Envio.objects.count() == 0
    assert OutboxEvent.objects.count() == 0


# ------------------------------------------------ 2. o envio nasce
def test_entregar_grava_o_envio_1_e_a_porta_vira_enviada(ana_pronta):
    envio = checkpoint.entregar(ana_pronta, **entrega())
    assert envio.numero == 1
    assert envio.estado == Envio.Estado.RECEBIDO
    assert envio.prazo_em == envio.enviado_em + timedelta(hours=24)
    assert envio.estourado_em is None
    assert envio.links == [{"rotulo": "Arquivo", "url": ARQUIVO}]
    assert envio.readme == README
    assert envio.laudo_do_aluno == {"texto": AUTOAVALIACAO}
    assert ana_pronta.estado == Progresso.Estado.ENVIADA
    assert Progresso.objects.get(pk=ana_pronta.pk).estado == Progresso.Estado.ENVIADA


def test_entregar_enfileira_envio_recebido_na_outbox(ana_pronta):
    envio = checkpoint.entregar(ana_pronta, **entrega())
    evento = OutboxEvent.objects.get()
    assert (evento.event, evento.version, evento.published_at) == (
        "envio.recebido",
        1,
        None,
    )
    assert evento.payload == {
        "site_id": "escola-a",
        "curso_id": str(envio.aula.curso_id),
        "aula_id": str(envio.aula_id),
        "envio_id": str(envio.pk),
        "numero": 1,
    }
    assert evento.envelope_extra == {"ator_id": "p_ana"}


# ------------------------------------------------ 3. o reenvio
def test_reenvio_so_a_partir_de_devolvida_e_recebe_o_numero_2(ana_pronta):
    primeiro = checkpoint.entregar(ana_pronta, **entrega())
    with pytest.raises(checkpoint.EnvioRecusado, match="já está na fila"):
        checkpoint.entregar(ana_pronta, **entrega())
    # O laudo devolve (degrau 2.2); aqui a porta é posta em `devolvida` à mão.
    Progresso.objects.filter(pk=ana_pronta.pk).update(estado=Progresso.Estado.DEVOLVIDA)
    ana_pronta.refresh_from_db()
    segundo = checkpoint.entregar(
        ana_pronta, **entrega(readme="Versão 2: a base ficou mais larga.")
    )
    assert (primeiro.numero, segundo.numero) == (1, 2)
    assert segundo.pk != primeiro.pk
    assert Envio.objects.count() == 2
    assert Progresso.objects.get(pk=ana_pronta.pk).estado == Progresso.Estado.ENVIADA
    numeros = OutboxEvent.objects.filter(event="envio.recebido").order_by("id")
    assert [evento.payload["numero"] for evento in numeros] == [1, 2]


# ------------------------------------------------ 4. o que se valida
@pytest.mark.parametrize(
    "links, frase",
    [
        ([], "Falta o link do arquivo"),
        ([{"rotulo": "Arquivo", "url": ""}], "Falta o link do arquivo"),
        ([{"rotulo": "Sólido", "url": SOLIDO}], "Falta o link do arquivo"),
        ([{"rotulo": "Arquivo", "url": "ftp://arquivos.exemplo.test/a"}], "http"),
        ([{"rotulo": "Arquivo", "url": "arquivos.exemplo.test/cubo.blend"}], "http"),
        ([{"rotulo": "Arquivo", "url": "https://" + "a" * 500}], "http"),
        (
            [{"rotulo": "Arquivo", "url": ARQUIVO}, {"rotulo": "", "url": SOLIDO}],
            "rótulo",
        ),
    ],
)
def test_links_precisam_de_url_http_de_rotulo_e_do_arquivo(ana_pronta, links, frase):
    with pytest.raises(checkpoint.EnvioRecusado, match=frase):
        checkpoint.entregar(ana_pronta, **entrega(links=links))
    assert Envio.objects.count() == 0


def test_previa_sem_link_e_pulada_e_previa_com_link_e_guardada(ana_pronta):
    envio = checkpoint.entregar(
        ana_pronta,
        **entrega(
            links=[
                {"rotulo": "Arquivo", "url": ARQUIVO},
                {"rotulo": "Sólido", "url": SOLIDO},
                {"rotulo": "Wireframe", "url": ""},
                {"rotulo": "", "url": ""},
            ]
        ),
    )
    assert envio.links == [
        {"rotulo": "Arquivo", "url": ARQUIVO},
        {"rotulo": "Sólido", "url": SOLIDO},
    ]


def test_o_readme_e_obrigatorio(ana_pronta):
    with pytest.raises(checkpoint.EnvioRecusado, match="README"):
        checkpoint.entregar(ana_pronta, **entrega(readme="   "))
    assert Envio.objects.count() == 0


def test_sem_instrumento_a_autoavaliacao_e_texto_livre_e_obrigatoria(ana_pronta):
    assert ana_pronta.aula.instrumento is None
    for laudo in (
        {"texto": " "},
        {},
        None,
        {"notas": {"x": {"nota": 5, "frase": "y"}}},
    ):
        with pytest.raises(checkpoint.EnvioRecusado, match="autoavaliação"):
            checkpoint.entregar(ana_pronta, **entrega(laudo_do_aluno=laudo))
    assert Envio.objects.count() == 0


ESCALA = {
    "Proporção": {"minimo": 1, "maximo": 5},
    "Acabamento": {"minimo": 1, "maximo": 5},
}


def notas(mudancas: dict | None = None) -> dict:
    base = {
        "Proporção": {"nota": 4, "frase": "As faces estão no tamanho do pedido."},
        "Acabamento": {"nota": 3, "frase": "O bevel ficou grande demais."},
    }
    base.update(mudancas or {})
    return {"notas": base}


@pytest.fixture
def com_instrumento(ana_pronta):
    """A E00 com o instrumento `studs`, escala de dois critérios, versão 3."""
    studs = Instrumento.objects.get(slug="studs")
    studs.escala = ESCALA
    studs.versao = 3
    studs.save()
    ana_pronta.aula.instrumento = studs
    ana_pronta.aula.save(update_fields=["instrumento"])
    return ana_pronta


@pytest.mark.parametrize(
    "laudo, frase",
    [
        # Sem "notas" nenhuma, o primeiro critério em ordem alfabética
        # (`criterios_de`) é quem acusa: Acabamento, não Proporção.
        ({"texto": "só texto"}, "Dê uma nota de 1 a 5 em Acabamento"),
        (notas({"Proporção": {"nota": 6, "frase": "x"}}), "1 a 5 em Proporção"),
        (notas({"Proporção": {"nota": 0, "frase": "x"}}), "1 a 5 em Proporção"),
        (notas({"Proporção": {"nota": "4", "frase": "x"}}), "1 a 5 em Proporção"),
        (notas({"Proporção": {"nota": True, "frase": "x"}}), "1 a 5 em Proporção"),
        (
            notas({"Acabamento": {"nota": 3, "frase": "  "}}),
            "frase para a nota de Acabamento",
        ),
        (notas({"Acabamento": None}), "1 a 5 em Acabamento"),
    ],
)
def test_com_instrumento_a_autoavaliacao_exige_nota_na_escala_e_frase(
    com_instrumento, laudo, frase
):
    with pytest.raises(checkpoint.EnvioRecusado, match=frase):
        checkpoint.entregar(com_instrumento, **entrega(laudo_do_aluno=laudo))
    assert Envio.objects.count() == 0


def test_com_instrumento_o_laudo_do_aluno_guarda_a_versao_em_que_comecou(
    com_instrumento,
):
    envio = checkpoint.entregar(com_instrumento, **entrega(laudo_do_aluno=notas()))
    assert envio.laudo_do_aluno == {
        "instrumento": "studs",
        "versao": 3,
        "notas": notas()["notas"],
    }


@pytest.mark.parametrize(
    "escala",
    [
        {},
        [],
        {"criterios": [1, 2]},
        {"Proporção": {"minimo": "1", "maximo": 5}},
        {"Proporção": {"minimo": 5, "maximo": 1}},
        {"Proporção": {"minimo": 3, "maximo": 3}},
        {"Proporção": {"minimo": True, "maximo": 5}},
        {"Proporção": [1, 5]},
    ],
)
def test_escala_ilegivel_nao_da_criterio_nenhum(escala):
    assert checkpoint.criterios_de(Instrumento(escala=escala)) == []
    assert checkpoint.criterios_de(None) == []


def test_escala_legivel_da_os_criterios_em_ordem_alfabetica():
    """Nunca "a ordem em que o JSON foi escrito": o `jsonb` do Postgres não
    preserva ordem de chave de objeto, e a tela e o serviço leem o instrumento
    em requisições separadas. Alfabético por nome é o que sobra determinístico."""
    assert checkpoint.criterios_de(Instrumento(escala=ESCALA)) == [
        checkpoint.Criterio("Acabamento", 1, 5),
        checkpoint.Criterio("Proporção", 1, 5),
    ]


# ------------------------------------------------ 5. a tela
def abrir(client, endereco):
    return client.get(endereco, HTTP_COOKIE=COOKIE)


def bloco_do_checkpoint(resposta) -> str:
    corpo = resposta.content.decode("utf-8")
    inicio = corpo.index('id="checkpoint"')
    return corpo[inicio : corpo.index("</section>", inicio)]


def entregar_pela_tela(client, **campos):
    return client.post(
        reverse("entregar-checkpoint", args=["E00"]),
        {**FORMULARIO, **campos},
        HTTP_COOKIE=COOKIE,
    )


def test_a_tela_so_mostra_o_formulario_quando_da_para_entregar(
    aluna, aula_publicada, client
):
    aula = reverse("aula-do-curso", args=["profissional", 1, "E00"])
    bloco = bloco_do_checkpoint(abrir(client, aula))
    assert "fica fechado até todas as pausas" in bloco
    assert "<form" not in bloco

    client.post(
        reverse("registrar-pausa", args=["E00", 1]),
        {"campo_0": "um cubo"},
        HTTP_COOKIE=COOKIE,
    )
    client.post(
        reverse("registrar-pausa", args=["E00", 2]),
        {"campo_0": "tentei", "campo_1": "aconteceu"},
        HTTP_COOKIE=COOKIE,
    )
    bloco = bloco_do_checkpoint(abrir(client, aula))
    assert "fica fechado" not in bloco
    assert "<form" in bloco
    assert 'name="arquivo"' in bloco
    assert 'name="previa_url_0"' in bloco and 'value="Sólido"' in bloco
    assert 'name="readme"' in bloco
    assert 'name="autoavaliacao"' in bloco
    assert "Envio 1" not in bloco


def test_entregar_pela_tela_grava_e_a_aula_diz_recebido_em_e_revisao_ate(
    aluna, ana_pronta, client
):
    resposta = entregar_pela_tela(client)
    assert resposta.status_code == 302
    # A volta é para o ENDEREÇO DO LIVRO (TAR-212), mesmo quando o gesto chegou
    # pelo endereço antigo: é ele que o aluno copia da barra do navegador.
    assert resposta["Location"] == reverse(
        "aula-do-curso", args=["profissional", 1, "E00"]
    ) + ("?recado=entregue#checkpoint")
    assert "meshcraft_sessao" not in resposta.cookies, "reescreveu o cookie do site"

    envio = Envio.objects.get()
    assert envio.links == [
        {"rotulo": "Arquivo", "url": ARQUIVO},
        {"rotulo": "Sólido", "url": SOLIDO},
    ]
    assert envio.readme == README
    assert envio.laudo_do_aluno == {"texto": AUTOAVALIACAO}

    resposta = abrir(
        client,
        reverse("aula-do-curso", args=["profissional", 1, "E00"]) + "?recado=entregue",
    )
    assert "meshcraft_sessao" not in resposta.cookies
    corpo = resposta.content.decode("utf-8")
    assert "Recebido. Seu envio entrou na fila de revisão" in corpo
    bloco = bloco_do_checkpoint(resposta)
    assert "Envio 1: Recebido" in bloco
    assert "Recebido em " in bloco and "Revisão até " in bloco
    assert ARQUIVO in bloco and SOLIDO in bloco
    assert "<form" not in bloco
    assert "já está na fila de revisão" in bloco


def test_a_hora_na_tela_e_a_de_sao_paulo(aluna, ana_pronta, client):
    envio = checkpoint.entregar(ana_pronta, **entrega())
    recebido = timezone.localtime(envio.enviado_em)
    prazo = timezone.localtime(envio.prazo_em)
    assert recebido.tzinfo.key == "America/Sao_Paulo"
    bloco = bloco_do_checkpoint(
        abrir(client, reverse("aula-do-curso", args=["profissional", 1, "E00"]))
    )
    assert f"Recebido em {recebido:%d/%m/%Y} às {recebido:%H:%M}." in bloco
    assert f"Revisão até {prazo:%d/%m/%Y} às {prazo:%H:%M}." in bloco


def test_a_recusa_volta_para_o_checkpoint_com_a_frase(aluna, ana_pronta, client):
    resposta = entregar_pela_tela(client, arquivo="")
    assert resposta.status_code == 302
    assert "?erro=" in resposta["Location"]
    assert resposta["Location"].endswith("#checkpoint")
    corpo = abrir(client, resposta["Location"]).content.decode("utf-8")
    assert "Falta o link do arquivo" in corpo
    assert Envio.objects.count() == 0
    assert (
        Progresso.objects.get(pk=ana_pronta.pk).estado == Progresso.Estado.EM_PRODUCAO
    )


def test_com_instrumento_a_tela_pede_nota_e_frase_por_criterio(
    aluna, com_instrumento, client
):
    """A ordem dos critérios é a alfabética do nome (`criterios_de`), nunca a
    ordem em que a escala foi escrita: Acabamento vem antes de Proporção, e por
    isso o índice 0 é Acabamento."""
    bloco = bloco_do_checkpoint(
        abrir(client, reverse("aula-do-curso", args=["profissional", 1, "E00"]))
    )
    assert "Proporção" in bloco and "Acabamento" in bloco
    assert 'name="nota_0"' in bloco and 'name="frase_0"' in bloco
    assert 'name="nota_1"' in bloco and 'name="frase_1"' in bloco
    assert 'name="autoavaliacao"' not in bloco
    assert bloco.count('<option value="') == 12  # "Nota" + 1..5, duas vezes

    campos = {
        "nota_0": "3",
        "frase_0": "O bevel ficou grande demais.",
        "nota_1": "",
        "frase_1": "x",
    }
    resposta = entregar_pela_tela(client, **campos)
    assert "erro=" in resposta["Location"]
    assert "1 a 5 em Proporção" in abrir(client, resposta["Location"]).content.decode()
    assert Envio.objects.count() == 0

    resposta = entregar_pela_tela(client, **{**campos, "nota_1": "4"})
    assert "recado=entregue" in resposta["Location"]
    assert Envio.objects.get().laudo_do_aluno == {
        "instrumento": "studs",
        "versao": 3,
        "notas": {
            "Acabamento": {"nota": 3, "frase": "O bevel ficou grande demais."},
            "Proporção": {"nota": 4, "frase": "x"},
        },
    }


def test_devolvida_reabre_o_formulario_como_reenvio(aluna, ana_pronta, client):
    checkpoint.entregar(ana_pronta, **entrega())
    Progresso.objects.filter(pk=ana_pronta.pk).update(estado=Progresso.Estado.DEVOLVIDA)
    bloco = bloco_do_checkpoint(
        abrir(client, reverse("aula-do-curso", args=["profissional", 1, "E00"]))
    )
    assert "Envio 1: Recebido" in bloco
    assert "<form" in bloco
    assert "Este é o envio 2" in bloco
    resposta = entregar_pela_tela(client)
    assert "recado=entregue" in resposta["Location"]
    assert Envio.objects.get(numero=2).pessoa_id == "p_ana"


def test_o_estouro_registrado_aparece_na_tela(aluna, ana_pronta, client):
    envio = checkpoint.entregar(ana_pronta, **entrega())
    checkpoint.registrar_estouros(envio.prazo_em + timedelta(hours=3))
    bloco = bloco_do_checkpoint(
        abrir(client, reverse("aula-do-curso", args=["profissional", 1, "E00"]))
    )
    assert "O prazo de revisão passou em" in bloco
    assert "continua na fila" in bloco
    assert "<form" not in bloco


def test_concluida_mostra_o_envio_e_nao_o_formulario(aluna, ana_pronta, client):
    checkpoint.entregar(ana_pronta, **entrega())
    Progresso.objects.filter(pk=ana_pronta.pk).update(
        estado=Progresso.Estado.CONCLUIDA, concluida_em=timezone.now()
    )
    bloco = bloco_do_checkpoint(
        abrir(client, reverse("aula-do-curso", args=["profissional", 1, "E00"]))
    )
    assert "Envio 1" in bloco
    assert "<form" not in bloco
    assert "já está concluída" in bloco


def test_visitante_e_sem_matricula_nao_entregam(
    env_dos_pares, rede, aula_publicada, client
):
    from tests.conftest import ANA, dublar_matricula, dublar_sessao

    assert (
        client.post(
            reverse("entregar-checkpoint", args=["E00"]), FORMULARIO
        ).status_code
        == 200
    )
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")
    resposta = entregar_pela_tela(client)
    assert resposta.status_code == 403
    assert Envio.objects.count() == 0
