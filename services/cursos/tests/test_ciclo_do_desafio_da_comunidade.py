"""Diagnóstico com prova (TAR-825, frente C4): o ciclo do desafio da
Comunidade Meshcraft, de ponta a ponta, com dados de teste.

Telas e rotas já existem (degraus 2.1 e 2.2). Este arquivo percorre o
ciclo inteiro pelas rotas HTTP reais, com a `alunos` dublada por `respx`
(molde: `tests/conftest.py`), e prova que cada estado da porta fala com o
membro numa frase própria: trancada, disponível, em produção, enviada (com
o relógio de 24 horas), devolvida (com a data), concluída, link inválido e
`alunos` fora do ar. Nenhuma frase de aluno usa a palavra "reprovado".

O roteiro (`RETOMADA-COMUNIDADE.md` §7, frente C4):
1. membro com matrícula ativa abre o mapa; a porta em destaque é o desafio
   (E00); a aula mostra "aceito quando" como lista de conferência.
2. envia o link (envio 1); estado `enviada`, com o relógio de 24 horas.
3. a professora (`CURSOS_PROFESSORES`) vê o envio em `/cursos/plantao`,
   ordenado por prazo, e abre a ficha.
4. assina laudo `devolvido`, com três forças, uma mudança e data de retorno.
5. o membro vê em `/cursos/<numero>/laudo` a data antes do texto; a aula
   mostra `devolvida` com a data.
6. reenvia (envio 2); o 1 continua visível (laudo anterior, ao lado, nas
   duas telas); recebe `aberto`; a porta seguinte abre; `aula.concluida.v1`
   sai UMA vez pela outbox.
"""

from __future__ import annotations

import datetime as dt
import re

import httpx
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cursos import envio as checkpoint_service
from apps.cursos.models import Aula, Envio, Laudo, OutboxEvent, Pessoa, Progresso
from tests.conftest import (
    ANA,
    ARQUIVO,
    AUTOAVALIACAO,
    COOKIE,
    README,
    dublar_matricula,
    dublar_sessao,
    entrega,
    publicar,
    url_das_matriculas,
)

pytestmark = pytest.mark.django_db

CURSO = "profissional"

# A professora de teste: uma identidade própria, fora da lista de alunos, que
# `CURSOS_PROFESSORES` autoriza a dar laudo. Ela não precisa de matrícula
# ([INV] "eh_professor não depende de eh_aluno").
PROFESSORA = {
    "autenticado": True,
    "id": "p_dani_plantao",
    "email": "dani.plantao@exemplo.com",
    "nome_exibido": "Dani",
    "papel": "professor",
}


def _como(rede, pessoa: dict, categoria: str = "cadastrado"):
    """Troca a identidade e a matrícula que a rede dublada devolve, para o
    PRÓXIMO pedido: as duas rotas são as mesmas para qualquer pessoa, e o
    teste avança pelos dois lados do plantão com a mesma `rede`."""
    dublar_sessao(rede, pessoa)
    dublar_matricula(rede, pessoa["email"], categoria)


def _form_de_entrega(**mudancas) -> dict:
    """Os campos do FORMULÁRIO HTML do checkpoint (`aula.html`), na forma que
    `entregar_checkpoint` lê do POST (`arquivo`, `readme`, `autoavaliacao`):
    é OUTRA forma da que `entrega()` de `conftest.py` monta para chamar
    `checkpoint.entregar()` direto, e a rota HTTP não lê aquela."""
    base = {"arquivo": ARQUIVO, "readme": README, "autoavaliacao": AUTOAVALIACAO}
    base.update(mudancas)
    return base


def _forcas_do_teste() -> list[str]:
    return [
        "O bevel das arestas ficou uniforme em todo o modelo.",
        "A escala bateu com a referência sem precisar de ajuste.",
        "O README explica o processo passo a passo.",
    ]


def _emitir_laudo(
    client, envio_id: int, *, decisao: str, aula_id, data_de_retorno=None
):
    corpo = {
        "forca_0": _forcas_do_teste()[0],
        "forca_1": _forcas_do_teste()[1],
        "forca_2": _forcas_do_teste()[2],
        "mudanca_texto": "Praticar UV na próxima entrega.",
        "mudanca_aula": str(aula_id),
        "decisao": decisao,
        "sabe_o_que_fazer_amanha": "sim",
    }
    if data_de_retorno is not None:
        corpo["data_de_retorno"] = data_de_retorno.isoformat()
    return client.post(
        reverse("plantao-ficha", args=[envio_id]), corpo, HTTP_COOKIE=COOKIE
    )


def test_o_ciclo_do_desafio_da_comunidade_de_ponta_a_ponta(
    env_dos_pares, rede, aula_publicada, client, monkeypatch
):
    e00 = aula_publicada
    curso = e00.curso
    parte = e00.bloco.parte
    corpos: list[str] = []

    def get(nome, *args):
        resposta = client.get(reverse(nome, args=list(args)), HTTP_COOKIE=COOKIE)
        corpos.append(resposta.content.decode())
        return resposta

    # ------------------------------------------------------------------ 1
    # O membro abre o mapa: a porta em destaque é o desafio (E00), publicado
    # e disponível para ela (a E00 nasce `disponivel` na primeira visita).
    _como(rede, ANA, "aluno")
    resposta = get("curso", CURSO)
    assert resposta.status_code == 200
    assert 'class="porta-atual"' in resposta.content.decode()
    assert e00.titulo_exibido in resposta.content.decode()

    # A aula mostra "aceito quando" como lista de conferência.
    resposta = get("aula-do-curso", CURSO, parte, e00.numero)
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert 'class="aceito-quando"' in corpo
    for criterio in e00.aceito_quando:
        assert criterio in corpo
    # A primeira abertura já levou `disponivel` a `em_producao` (armadilhas
    # da própria célula, `progresso.abrir`): o rótulo na lista de aulas prova.
    assert "Em andamento" in corpo

    # As duas pausas da aula publicada (molde `publicar()`) são pré-condição
    # do checkpoint: sem elas a entrega é recusada.
    for pausa in e00.pausas.all():
        resposta_pausa = client.post(
            reverse(
                "registrar-pausa-do-curso", args=[CURSO, parte, e00.numero, pausa.ordem]
            ),
            {f"campo_{i}": "registrado" for i in range(len(pausa.campos))},
            HTTP_COOKIE=COOKIE,
        )
        assert resposta_pausa.status_code == 302

    # ---------------------------------------------------- link inválido
    # Um link sem esquema é recusado com a frase de `envio.py`, e a porta
    # continua em produção: nenhum envio nasce da tentativa.
    resposta_recusa = client.post(
        reverse("entregar-checkpoint-do-curso", args=[CURSO, parte, e00.numero]),
        _form_de_entrega(arquivo="isto-nao-e-um-link"),
        HTTP_COOKIE=COOKIE,
    )
    assert resposta_recusa.status_code == 302
    # POST-redirect-GET: o erro viaja na query do redirect (`_voltar_a_aula`),
    # e só aparece seguindo o `Location`, nunca num GET novo e limpo.
    resposta = client.get(resposta_recusa["Location"], HTTP_COOKIE=COOKIE)
    corpos.append(resposta.content.decode())
    corpo = resposta.content.decode()
    assert "precisa ser um endereço completo, começando com http" in corpo
    assert Envio.objects.count() == 0

    # ------------------------------------------------------------------ 2
    # O envio 1, de verdade: a porta vira `enviada`, com o relógio de 24h.
    resposta_entrega = client.post(
        reverse("entregar-checkpoint-do-curso", args=[CURSO, parte, e00.numero]),
        _form_de_entrega(),
        HTTP_COOKIE=COOKIE,
    )
    assert resposta_entrega.status_code == 302
    envio_1 = Envio.objects.get(numero=1)
    assert envio_1.estado == Envio.Estado.RECEBIDO

    resposta = get("aula-do-curso", CURSO, parte, e00.numero)
    corpo = resposta.content.decode()
    assert "Enviada" in corpo
    # O relógio: a data e a hora exatas da revisão, não a palavra "24 horas"
    # (essa só aparece no recado efêmero de quem acabou de entregar).
    assert timezone.localtime(envio_1.prazo_em).strftime("%d/%m/%Y") in corpo
    assert "Revisão até" in corpo

    resposta = get("curso", CURSO)
    corpo = resposta.content.decode()
    assert "fila de revisão" in corpo
    assert "24 horas" in corpo

    # ------------------------------------------------------------------ 3
    # A professora vê o envio no plantão, ordenado por prazo, e abre a ficha.
    monkeypatch.setenv("CURSOS_PROFESSORES", PROFESSORA["email"])
    _como(rede, PROFESSORA)
    resposta = get("plantao")
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert e00.titulo_exibido in corpo
    posicao_envio_1 = corpo.find(f"envio {envio_1.numero}")
    assert posicao_envio_1 != -1

    resposta = get("plantao-ficha", envio_1.id)
    assert resposta.status_code == 200
    assert "Emitir laudo" in resposta.content.decode()

    # ------------------------------------------------------------------ 4
    # Ela assina o laudo `devolvido`: três forças, uma mudança, data de
    # retorno de amanhã em diante.
    amanha = timezone.localdate() + dt.timedelta(days=2)
    resposta_laudo = _emitir_laudo(
        client,
        envio_1.id,
        decisao=Laudo.Decisao.DEVOLVIDO,
        aula_id=e00.id,
        data_de_retorno=amanha,
    )
    assert resposta_laudo.status_code == 302
    laudo_1 = Laudo.objects.get(envio=envio_1)
    assert laudo_1.decisao == Laudo.Decisao.DEVOLVIDO
    assert laudo_1.data_de_retorno == amanha
    assert len(laudo_1.forcas) == 3

    # ------------------------------------------------------------------ 5
    # O membro vê a data ANTES do texto (lei §6), e a aula mostra `devolvida`
    # com a data. Nenhuma frase de aluno usa "reprovado".
    _como(rede, ANA, "aluno")
    resposta = get("laudo-recebido", e00.numero)
    corpo = resposta.content.decode()
    data_formatada = amanha.strftime("%d/%m/%Y")
    posicao_da_data = corpo.find(data_formatada)
    posicao_do_texto = corpo.find("Praticar UV na próxima entrega.")
    assert posicao_da_data != -1 and posicao_do_texto != -1
    assert posicao_da_data < posicao_do_texto

    resposta = get("aula-do-curso", CURSO, parte, e00.numero)
    corpo = resposta.content.decode()
    assert "Devolvida" in corpo
    assert "envio anterior foi devolvido" in corpo

    resposta = get("curso", CURSO)
    corpo = resposta.content.decode()
    assert data_formatada in corpo

    # ------------------------------------------------------------------ 6
    # Reenvia: envio 2, numerado; o 1 continua existindo (histórico).
    resposta_reenvio = client.post(
        reverse("entregar-checkpoint-do-curso", args=[CURSO, parte, e00.numero]),
        _form_de_entrega(readme=README + " Reenvio com o ajuste pedido."),
        HTTP_COOKIE=COOKIE,
    )
    assert resposta_reenvio.status_code == 302
    envio_2 = Envio.objects.get(numero=2)
    assert Envio.objects.filter(pessoa=envio_1.pessoa, aula=e00).count() == 2
    assert Envio.objects.filter(pk=envio_1.pk).exists()

    # A professora abre o reenvio: o laudo anterior (devolvido) está ao lado,
    # nas duas telas do plantão (fila e ficha) — o envio 1 continua visível.
    monkeypatch.setenv("CURSOS_PROFESSORES", PROFESSORA["email"])
    _como(rede, PROFESSORA)
    resposta = get("plantao")
    corpo = resposta.content.decode()
    assert "Este é um reenvio" in corpo
    assert "Praticar UV na próxima entrega." in corpo

    resposta = get("plantao-ficha", envio_2.id)
    corpo = resposta.content.decode()
    assert "O laudo anterior" in corpo
    assert "Praticar UV na próxima entrega." in corpo

    # Ela abre com o laudo `aberto`: a porta seguinte abre, e o evento sai.
    resposta_laudo_2 = _emitir_laudo(
        client, envio_2.id, decisao=Laudo.Decisao.ABERTO, aula_id=e00.id
    )
    assert resposta_laudo_2.status_code == 302
    laudo_2 = Laudo.objects.get(envio=envio_2)
    assert laudo_2.decisao == Laudo.Decisao.ABERTO

    # `aula.concluida.v1` sai UMA vez pela outbox, nunca duas.
    assert OutboxEvent.objects.filter(event="aula.concluida").count() == 1

    proxima = Aula.objects.get(curso=curso, ordem=e00.ordem + 1)
    # A aula seguinte precisa estar publicada: rascunho aparece no mapa como
    # "Em preparo", sem link, mesmo com a porta destrancada.
    publicar(proxima)
    ana_pessoa = Pessoa.objects.get(id_da_plataforma=ANA["id"])
    progresso_seguinte = Progresso.objects.get(pessoa=ana_pessoa, aula=proxima)
    assert progresso_seguinte.estado == Progresso.Estado.DISPONIVEL

    progresso_e00 = Progresso.objects.get(pessoa=ana_pessoa, aula=e00)
    assert progresso_e00.estado == Progresso.Estado.CONCLUIDA
    assert progresso_e00.concluida_em is not None

    # O membro, de volta: o laudo novo (aberto) e o anterior (devolvido) ao
    # lado, e a porta seguinte já aparece aberta no mapa.
    _como(rede, ANA, "aluno")
    resposta = get("laudo-recebido", e00.numero)
    corpo = resposta.content.decode()
    assert "As bordas ficaram consistentes." not in corpo  # sem rubrica aqui
    assert "Praticar UV na próxima entrega." in corpo
    assert "O envio anterior" in corpo
    assert "Envios anteriores" in corpo
    assert "Envio 1" in corpo

    resposta = get("curso", CURSO)
    corpo = resposta.content.decode()
    # O link só existe quando a porta abre; porta trancada imprime o título
    # sem href (mapa.html). Conferir o título seria tautológico.
    assert (
        reverse("aula-do-curso", args=[CURSO, proxima.bloco.parte, proxima.numero])
        in corpo
    )
    assert corpo.count(">Concluída<") == 1

    # ---------------------------------------------------- alunos fora do ar
    # Fecha por completo, nunca "pode entrar": nem por engano vira aluno.
    rota = rede.get(url_das_matriculas(ANA["email"]))
    rota.mock(side_effect=httpx.ConnectError("alunos fora do ar"))
    resposta = get("curso", CURSO)
    corpos.append(resposta.content.decode())
    assert resposta.status_code == 403
    assert "Não conseguimos conferir sua matrícula agora" in resposta.content.decode()

    # ------------------------------------------------------- INV-CUR-L2
    # Em NENHUMA das telas de aluno a palavra proibida aparece.
    for corpo in corpos:
        assert "reprovad" not in corpo.lower()


def test_cada_estado_de_porta_tem_frase_propria_no_mapa(aluna, esqueleto, client):
    """[TAR-825] Cada estado de porta fala com o membro numa frase própria:
    até esta prova, `disponivel`, `em_producao`, `enviada`, `devolvida` e
    `concluida` compartilhavam a MESMA frase no mapa ("Aula publicada e
    disponível para você."), e a diferença só aparecia dentro da aula."""
    aulas = list(esqueleto.aulas.order_by("ordem")[:5])
    for uma_aula in aulas:
        publicar(uma_aula)
    ana = Pessoa.objects.create(id_da_plataforma=ANA["id"], nome_exibido="Ana")
    amanha = timezone.localdate() + dt.timedelta(days=2)
    estados = [
        (Progresso.Estado.DISPONIVEL, {}),
        (Progresso.Estado.EM_PRODUCAO, {}),
        (Progresso.Estado.ENVIADA, {}),
        (Progresso.Estado.DEVOLVIDA, {"data_de_retorno": amanha}),
        (Progresso.Estado.CONCLUIDA, {"concluida_em": timezone.now()}),
    ]
    for uma_aula, (estado, extra) in zip(aulas, estados):
        Progresso.objects.create(pessoa=ana, aula=uma_aula, estado=estado, **extra)

    resposta = client.get(reverse("curso", args=[CURSO]), HTTP_COOKIE=COOKIE)
    corpo = resposta.content.decode()
    frases = re.findall(r'<span class="miudo">([^<]*)</span>', corpo)
    cinco_primeiras = frases[:5]
    assert len(cinco_primeiras) == 5
    assert (
        len(set(cinco_primeiras)) == 5
    ), "as cinco frases precisam ser diferentes; vieram: " + repr(cinco_primeiras)
    assert "24 horas" in cinco_primeiras[2]
    assert amanha.strftime("%d/%m/%Y") in cinco_primeiras[3]


def test_o_estouro_do_prazo_aparece_para_o_aluno(aluna, ana_pronta, client):
    """[roteiro 7] `enviada` com o prazo estourado tem frase própria, e o
    envio continua na fila (`registrar_estouros` não altera o estado)."""
    envio = checkpoint_service.entregar(ana_pronta, **entrega())
    depois_do_prazo = envio.prazo_em + dt.timedelta(hours=2)
    checkpoint_service.registrar_estouros(depois_do_prazo)
    envio.refresh_from_db()
    assert envio.estourado_em is not None

    aula = ana_pronta.aula
    resposta = client.get(
        reverse("aula-do-curso", args=[CURSO, aula.bloco.parte, aula.numero]),
        HTTP_COOKIE=COOKIE,
    )
    corpo = resposta.content.decode()
    assert "O prazo de revisão passou em" in corpo
    assert "o laudo chega assim que a professora o abrir" in corpo
    assert "reprovad" not in corpo.lower()
