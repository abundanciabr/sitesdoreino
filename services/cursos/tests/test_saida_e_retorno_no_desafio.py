"""Prova de integração (TAR-913, frente A3): o desafio da Comunidade fecha
quando a matrícula para de valer e reabre quando ela volta a valer, sem
conceder nada além do direito já vigente (matrícula ativa decide acesso, só a
professora assina laudo).

**O que este arquivo prova, e não outra coisa:** a `alunos` já filtra por
status antes de responder (`services/alunos/apps/core/api.py::list_enrollments`,
`Matricula.STATUS_QUE_VALEM = (STATUS_ATIVA,)`): suspensa, encerrada e
reembolsada nunca aparecem em `listEnrollments`, e a porta desta célula
(`apps/core/clients.py::AlunosClient.matriculas_de`, `apps/core/sessao.py`)
já trata "nenhuma matrícula que vale" como fail-closed. O que faltava provar é
o CICLO com histórico real: um membro que já entregou e já recebeu laudo,
perde o direito, tenta de novo, e recupera o direito depois.

**O texto de `https://meshcraft.top/docs/comunidade` confere com o
comportamento medido aqui**: "Termina a matrícula, termina a participação
ativa. Sem prazo escondido e sem condição nova" (o fechamento é total, não só
"sem desafio novo") e "Quem volta a ter matrícula ativa volta a participar.
O histórico e os reconhecimentos anteriores permanecem" (nada se apaga, e o
que volta é exatamente o que já existia). Nenhuma descoberta para a célula
admin.

Molde: `tests/test_ciclo_do_desafio_da_comunidade.py` (o ciclo completo,
matrícula sempre ativa) e `tests/test_acesso_pela_matricula.py` (o fail-closed
genérico, sem histórico prévio). Este arquivo soma os dois: histórico real +
saída e retorno.
"""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cursos.models import Envio, Laudo, OutboxEvent
from tests.conftest import (
    ANA,
    ARQUIVO,
    AUTOAVALIACAO,
    COOKIE,
    README,
    dublar_matricula,
    dublar_sessao,
    url_das_matriculas,
)

pytestmark = pytest.mark.django_db

CURSO = "profissional"

# As mesmas frases de `test_acesso_pela_matricula.py`: o texto é contrato com
# quem lê, e um teste que inventasse a própria frase não provaria que É esta
# que a pessoa vê.
A_FRASE_DE_SEM_MATRICULA = "Não encontramos uma matrícula ativa no seu nome"
A_FRASE_DE_SEM_RESPOSTA = "Não conseguimos conferir sua matrícula agora"

PROFESSORA = {
    "autenticado": True,
    "id": "p_dani_plantao",
    "email": "dani.plantao@exemplo.com",
    "nome_exibido": "Dani",
    "papel": "professor",
}

MUDANCA_DO_LAUDO = "Praticar UV na próxima entrega."


def _form_de_entrega(**mudancas) -> dict:
    base = {"arquivo": ARQUIVO, "readme": README, "autoavaliacao": AUTOAVALIACAO}
    base.update(mudancas)
    return base


def _entregar_o_desafio(client, e00, parte) -> Envio:
    """Abre a aula (nasce o progresso), registra as duas pausas e entrega o
    checkpoint. Devolve o `Envio` nascido, numerado 1."""
    resposta_aula = client.get(
        reverse("aula-do-curso", args=[CURSO, parte, e00.numero]), HTTP_COOKIE=COOKIE
    )
    assert resposta_aula.status_code == 200
    for pausa in e00.pausas.all():
        resposta_pausa = client.post(
            reverse(
                "registrar-pausa-do-curso", args=[CURSO, parte, e00.numero, pausa.ordem]
            ),
            {f"campo_{i}": "registrado" for i in range(len(pausa.campos))},
            HTTP_COOKIE=COOKIE,
        )
        assert resposta_pausa.status_code == 302
    resposta_entrega = client.post(
        reverse("entregar-checkpoint-do-curso", args=[CURSO, parte, e00.numero]),
        _form_de_entrega(),
        HTTP_COOKIE=COOKIE,
    )
    assert resposta_entrega.status_code == 302
    return Envio.objects.get(numero=1)


def _emitir_laudo_devolvido(client, envio: Envio, *, aula_id, data_de_retorno) -> Laudo:
    corpo = {
        "forca_0": "O bevel das arestas ficou uniforme em todo o modelo.",
        "forca_1": "A escala bateu com a referência sem precisar de ajuste.",
        "forca_2": "O README explica o processo passo a passo.",
        "mudanca_texto": MUDANCA_DO_LAUDO,
        "mudanca_aula": str(aula_id),
        "decisao": Laudo.Decisao.DEVOLVIDO,
        "sabe_o_que_fazer_amanha": "sim",
        "data_de_retorno": data_de_retorno.isoformat(),
    }
    resposta = client.post(
        reverse("plantao-ficha", args=[envio.id]), corpo, HTTP_COOKIE=COOKIE
    )
    assert resposta.status_code == 302
    return Laudo.objects.get(envio=envio)


def _preparar_historico(rede, aula_publicada, client, monkeypatch):
    """Ana, com matrícula ativa, entrega o desafio e recebe um laudo
    `devolvido`. Devolve `(e00, parte, envio, laudo, amanha)`, com o envio e o
    laudo já gravados: é o histórico que a saída e o retorno vão preservar."""
    e00 = aula_publicada
    parte = e00.bloco.parte

    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    envio = _entregar_o_desafio(client, e00, parte)

    monkeypatch.setenv("CURSOS_PROFESSORES", PROFESSORA["email"])
    dublar_sessao(rede, PROFESSORA)
    dublar_matricula(rede, PROFESSORA["email"], "cadastrado")
    amanha = timezone.localdate() + dt.timedelta(days=2)
    laudo = _emitir_laudo_devolvido(
        client, envio, aula_id=e00.id, data_de_retorno=amanha
    )
    # `emitir` grava `envio.estado`; a cópia em memória precisa acompanhar,
    # senão o teste compara o snapshot de ANTES do laudo com o de depois.
    envio.refresh_from_db()

    # De volta a Ana, matrícula ainda ativa: é o estado do qual a saída parte.
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    return e00, parte, envio, laudo, amanha


@pytest.mark.parametrize("categoria", ["suspensa", "encerrada"])
def test_matricula_suspensa_ou_encerrada_fecha_o_desafio_e_ativa_de_novo_reabre_com_historico_intacto(
    env_dos_pares, rede, aula_publicada, client, monkeypatch, categoria
):
    e00, parte, envio, laudo, amanha = _preparar_historico(
        rede, aula_publicada, client, monkeypatch
    )
    data_formatada = amanha.strftime("%d/%m/%Y")

    contagens_antes = {
        "envios": Envio.objects.count(),
        "laudos": Laudo.objects.count(),
        "eventos": OutboxEvent.objects.count(),
    }
    prazo_em_antes = envio.prazo_em
    estado_antes = envio.estado
    decisao_antes = laudo.decisao

    # ---------------------------------------------------- matrícula PARA
    # `categoria` é "suspensa" ou "encerrada": a `alunos` de verdade só
    # devolve status `ativa` em `listEnrollments` (`STATUS_QUE_VALEM`), então
    # as duas produzem o MESMO 404 que a porta desta célula já trata como
    # "nenhuma matrícula que vale" (`dublar_matricula`, `tests/conftest.py`).
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], categoria)

    resposta_aula = client.get(
        reverse("aula-do-curso", args=[CURSO, parte, e00.numero]), HTTP_COOKIE=COOKIE
    )
    assert resposta_aula.status_code == 403, categoria
    assert A_FRASE_DE_SEM_MATRICULA in resposta_aula.content.decode()

    # O envio recusado: nem uma tentativa de reenvio nasce com a matrícula
    # parada.
    resposta_envio_recusado = client.post(
        reverse("entregar-checkpoint-do-curso", args=[CURSO, parte, e00.numero]),
        _form_de_entrega(readme="Tentativa com a matrícula parada."),
        HTTP_COOKIE=COOKIE,
    )
    assert resposta_envio_recusado.status_code == 403, categoria
    assert A_FRASE_DE_SEM_MATRICULA in resposta_envio_recusado.content.decode()

    # O laudo antigo: some da TELA (a mesma porta que fecha o desafio fecha
    # a tela do laudo), mas continua intacto no banco, e a prova disso segue.
    resposta_laudo = client.get(
        reverse("laudo-recebido", args=[e00.numero]), HTTP_COOKIE=COOKIE
    )
    assert resposta_laudo.status_code == 403, categoria
    assert A_FRASE_DE_SEM_MATRICULA in resposta_laudo.content.decode()

    envio.refresh_from_db()
    laudo.refresh_from_db()
    assert envio.estado == estado_antes
    assert envio.prazo_em == prazo_em_antes
    assert laudo.decisao == decisao_antes
    assert laudo.data_de_retorno == amanha
    assert Envio.objects.count() == contagens_antes["envios"], categoria
    assert Laudo.objects.count() == contagens_antes["laudos"], categoria
    assert OutboxEvent.objects.count() == contagens_antes["eventos"], categoria

    # ---------------------------------------------- matrícula ativa de novo
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")

    resposta_aula_de_volta = client.get(
        reverse("aula-do-curso", args=[CURSO, parte, e00.numero]), HTTP_COOKIE=COOKIE
    )
    assert resposta_aula_de_volta.status_code == 200, categoria
    corpo_aula = resposta_aula_de_volta.content.decode()
    assert "Devolvida" in corpo_aula
    assert "envio anterior foi devolvido" in corpo_aula

    # O mapa mostra a data de retorno, como no ciclo normal (sem a saída).
    resposta_mapa = client.get(reverse("curso", args=[CURSO]), HTTP_COOKIE=COOKIE)
    assert resposta_mapa.status_code == 200, categoria
    assert data_formatada in resposta_mapa.content.decode()

    resposta_laudo_de_volta = client.get(
        reverse("laudo-recebido", args=[e00.numero]), HTTP_COOKIE=COOKIE
    )
    assert resposta_laudo_de_volta.status_code == 200, categoria
    corpo_laudo = resposta_laudo_de_volta.content.decode()
    assert MUDANCA_DO_LAUDO in corpo_laudo
    assert data_formatada in corpo_laudo

    # A volta não cria laudo, prazo nem evento novo: é o MESMO envio e o
    # MESMO laudo de antes, nunca outro.
    envio.refresh_from_db()
    assert envio.prazo_em == prazo_em_antes
    assert Envio.objects.count() == contagens_antes["envios"], categoria
    assert Laudo.objects.filter(envio=envio).count() == 1, categoria
    assert Laudo.objects.count() == contagens_antes["laudos"], categoria
    assert OutboxEvent.objects.count() == contagens_antes["eventos"], categoria


def test_alunos_fora_do_ar_fecha_o_desafio_com_historico_ja_existente_e_reabre_depois(
    env_dos_pares, rede, aula_publicada, client, monkeypatch
):
    """[item 3 do brief] "Alunos fora do ar" fecha do mesmo jeito que
    matrícula parada, mesmo havendo histórico: não conseguir perguntar nunca
    vira "então pode entrar" (`apps/core/sessao.py::_resolver`)."""
    e00, parte, envio, laudo, amanha = _preparar_historico(
        rede, aula_publicada, client, monkeypatch
    )

    contagens_antes = {
        "envios": Envio.objects.count(),
        "laudos": Laudo.objects.count(),
    }

    rota = rede.get(url_das_matriculas(ANA["email"]))
    rota.mock(side_effect=httpx.ConnectError("alunos fora do ar"))

    resposta_aula = client.get(
        reverse("aula-do-curso", args=[CURSO, parte, e00.numero]), HTTP_COOKIE=COOKIE
    )
    assert resposta_aula.status_code == 403
    assert A_FRASE_DE_SEM_RESPOSTA in resposta_aula.content.decode()

    resposta_laudo = client.get(
        reverse("laudo-recebido", args=[e00.numero]), HTTP_COOKIE=COOKIE
    )
    assert resposta_laudo.status_code == 403
    assert A_FRASE_DE_SEM_RESPOSTA in resposta_laudo.content.decode()

    envio.refresh_from_db()
    laudo.refresh_from_db()
    assert Envio.objects.count() == contagens_antes["envios"]
    assert Laudo.objects.count() == contagens_antes["laudos"]

    # A `alunos` volta ao ar, com matrícula ativa: reabre, histórico intacto.
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    resposta_de_volta = client.get(
        reverse("laudo-recebido", args=[e00.numero]), HTTP_COOKIE=COOKIE
    )
    assert resposta_de_volta.status_code == 200
    assert MUDANCA_DO_LAUDO in resposta_de_volta.content.decode()
