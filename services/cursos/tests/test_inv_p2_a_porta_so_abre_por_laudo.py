"""Teste-guarda [INV-CUR-P2]: a porta abre por UMA de duas regras, e a regra
é dado do curso. No curso por laudo (o padrão, e o do livro), só por laudo
`aberto` ou `aberto_com_ajuste`; no curso de progressão livre, só pelo gesto
do próprio aluno, com as pausas registradas. Em nenhum dos dois por data, por
XP ou por pagamento; o acesso ao curso é a matrícula, e só.

Lei: `PLANO-CELULA-CURSOS.md` §9 ("é o INV-GAM3 da gamificação visto do lado
da aula"); missão da célula ("o checkpoint abre a porta; o calendário,
nunca"); a segunda regra, `DECISAO-a-sala-serve-varios-cursos.md` §3
(07/09/2026, TAR-270). `progresso.concluir` EXIGE um laudo, e
`progresso.concluir_por_gesto` EXIGE o curso livre e as pausas; cada uma
recusa o curso da outra, e as duas gravam pelo mesmo miolo.

Os dentes, e o que cada um mede:

1. **Sem laudo, com laudo devolvido, ou com decisão que não existe: recusa**,
   e a porta seguinte continua trancada.
2. **Com laudo aberto: conclui**, carimba a hora, e abre a porta de `ordem + 1`.
3. **A assinatura de `concluir` não tem parâmetro de data, XP nem pagamento**,
   e é keyword-only: não dá para passar uma data no lugar do laudo.
4. **Data não abre porta**: gravar `data_de_retorno` não muda `estado`, e a
   tela recusa a aula seguinte enquanto a anterior não concluir.
5. **Nenhuma view grava `concluida`**: medido no código das telas.
6. **A EB não tranca ninguém e não é trancada pela E32**: abre quando a E32
   conclui; a E32 abre quando a E31 conclui, sem olhar para a EB.
7. **O gesto do curso livre**: recusa o curso por laudo (e o laudo recusa o
   curso livre); recusa com pausa faltando; recusa a porta trancada; abre só
   a `ordem + 1`; é idempotente e não emite duas vezes; emite
   `aula.concluida.v1` dentro da transação; a assinatura não tem laudo, data,
   XP nem pagamento.

Provado por mutação em 05/09/2026: apagar a exigência do laudo em
`progresso.concluir` deixa os oito casos do dente 1 vermelhos (8 failed, 15
passed); trocar `ordem + 1` por `ordem + 2` deixa a vizinhança e a bônus
vermelhas (6 failed, 17 passed). Restaurado, 23 passed. Em 07/09/2026: apagar
a exigência de `livre` em `concluir_por_gesto` deixa 1 vermelho; apagar a
exigência das pausas deixa 1 vermelho (a contagem está no PR da TAR-270).
"""

from __future__ import annotations

import datetime as dt
import inspect
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.urls import reverse

from apps.cursos import progresso as portas
from apps.cursos.models import (
    Aula,
    Bloco,
    Curso,
    OutboxEvent,
    Pessoa,
    Progresso,
    RegistroDePausa,
)
from tests.conftest import COOKIE, SITE, publicar

pytestmark = pytest.mark.django_db

ABERTO = SimpleNamespace(decisao="aberto")
ABERTO_COM_AJUSTE = SimpleNamespace(decisao="aberto_com_ajuste")
DEVOLVIDO = SimpleNamespace(decisao="devolvido")


@pytest.fixture
def ana(esqueleto):
    return Pessoa.objects.create(id_da_plataforma="p_ana", nome_exibido="Ana")


def aula(esqueleto, numero: str) -> Aula:
    return esqueleto.aulas.get(numero=numero)


def porta(pessoa, a: Aula, estado=Progresso.Estado.EM_PRODUCAO) -> Progresso:
    return Progresso.objects.create(pessoa=pessoa, aula=a, estado=estado)


def estado_de(pessoa, a: Aula) -> str:
    linha = portas.progresso_de(pessoa, a)
    return linha.estado if linha else Progresso.Estado.TRANCADA


# ------------------------------------------------------ 1. o que NÃO abre
@pytest.mark.parametrize(
    "laudo",
    [
        pytest.param(None, id="sem laudo"),
        pytest.param(DEVOLVIDO, id="devolvido"),
        pytest.param(SimpleNamespace(decisao="aprovado"), id="decisão inventada"),
        pytest.param(SimpleNamespace(decisao=None), id="None"),
        pytest.param(SimpleNamespace(nota=10), id="objeto sem decisão"),
        pytest.param(dt.date.today(), id="uma data no lugar do laudo"),
        pytest.param(100, id="XP no lugar do laudo"),
        pytest.param({"pago": True}, id="pagamento no lugar do laudo"),
    ],
)
def test_sem_laudo_aberto_a_porta_nao_conclui_nem_abre_a_seguinte(
    esqueleto, ana, laudo
):
    e00 = porta(ana, aula(esqueleto, "E00"))
    with pytest.raises(portas.PortaRecusada):
        portas.concluir(e00, laudo=laudo)
    e00.refresh_from_db()
    assert e00.estado == Progresso.Estado.EM_PRODUCAO
    assert e00.concluida_em is None
    assert estado_de(ana, aula(esqueleto, "E01")) == Progresso.Estado.TRANCADA


def test_porta_trancada_nao_conclui_nem_com_laudo(esqueleto, ana):
    e05 = porta(ana, aula(esqueleto, "E05"), Progresso.Estado.TRANCADA)
    with pytest.raises(portas.PortaRecusada):
        portas.concluir(e05, laudo=ABERTO)
    e05.refresh_from_db()
    assert e05.estado == Progresso.Estado.TRANCADA


# ----------------------------------------------------------- 2. o que abre
@pytest.mark.parametrize(
    "laudo", [ABERTO, ABERTO_COM_AJUSTE], ids=["aberto", "com ajuste"]
)
def test_com_laudo_aberto_a_porta_conclui_e_a_seguinte_abre(esqueleto, ana, laudo):
    e00 = porta(ana, aula(esqueleto, "E00"))
    portas.concluir(e00, laudo=laudo)
    e00.refresh_from_db()
    assert e00.estado == Progresso.Estado.CONCLUIDA
    assert e00.concluida_em is not None
    assert estado_de(ana, aula(esqueleto, "E01")) == Progresso.Estado.DISPONIVEL
    assert estado_de(ana, aula(esqueleto, "E02")) == Progresso.Estado.TRANCADA


def test_concluir_duas_vezes_e_inerte(esqueleto, ana):
    e00 = porta(ana, aula(esqueleto, "E00"))
    portas.concluir(e00, laudo=ABERTO)
    primeira = Progresso.objects.get(pk=e00.pk).concluida_em
    portas.concluir(e00, laudo=ABERTO)
    assert Progresso.objects.get(pk=e00.pk).concluida_em == primeira
    assert Progresso.objects.filter(pessoa=ana).count() == 2


def test_a_porta_n_so_sai_de_trancada_quando_a_n_menos_1_conclui(esqueleto, ana):
    """A vizinhança inteira, uma porta por vez: concluir a E03 não abre a E05."""
    e03 = porta(ana, aula(esqueleto, "E03"))
    portas.concluir(e03, laudo=ABERTO)
    assert estado_de(ana, aula(esqueleto, "E04")) == Progresso.Estado.DISPONIVEL
    assert estado_de(ana, aula(esqueleto, "E05")) == Progresso.Estado.TRANCADA
    assert estado_de(ana, aula(esqueleto, "E02")) == Progresso.Estado.TRANCADA


def test_a_cerimonia_fica_pendente_no_modelo_quando_a_aula_e_boss(esqueleto, ana):
    """O estado que a tentação poria em `request.session` (`armadilhas/143`)."""
    e02 = aula(esqueleto, "E02")
    e02.e_boss = True
    e02.save(update_fields=["e_boss"])
    linha = porta(ana, e02)
    portas.concluir(linha, laudo=ABERTO)
    linha.refresh_from_db()
    assert linha.cerimonia_pendente is True
    e00 = porta(ana, aula(esqueleto, "E00"))
    portas.concluir(e00, laudo=ABERTO)
    e00.refresh_from_db()
    assert e00.cerimonia_pendente is False


# ------------------------------------------------- 3. a assinatura fechada
def test_concluir_so_aceita_o_laudo_e_por_nome():
    parametros = inspect.signature(portas.concluir).parameters
    assert list(parametros) == ["progresso", "laudo"]
    assert parametros["laudo"].kind is inspect.Parameter.KEYWORD_ONLY
    for proibido in ("data", "xp", "pontos", "pagamento", "pago", "forcar", "force"):
        assert proibido not in parametros


def test_uma_data_na_posicao_do_laudo_nem_chega_a_ser_lida(esqueleto, ana):
    e00 = porta(ana, aula(esqueleto, "E00"))
    with pytest.raises(TypeError):
        portas.concluir(e00, dt.date.today())


# ------------------------------------------------------- 4. data não abre
def test_data_de_retorno_gravada_nao_muda_o_estado(esqueleto, ana):
    e00 = porta(ana, aula(esqueleto, "E00"), Progresso.Estado.DEVOLVIDA)
    e00.data_de_retorno = dt.date.today() - dt.timedelta(days=30)
    e00.save()
    e00.refresh_from_db()
    assert e00.estado == Progresso.Estado.DEVOLVIDA
    assert estado_de(ana, aula(esqueleto, "E01")) == Progresso.Estado.TRANCADA


def test_pela_tela_a_aula_seguinte_fica_trancada_ate_o_laudo(aluna, esqueleto, client):
    """A prova de FORA: mesmo publicada, a E01 volta ao mapa até a E00 concluir."""
    publicar(aula(esqueleto, "E00"))
    publicar(aula(esqueleto, "E01"))
    client.get(
        reverse("aula-do-curso", args=["profissional", 1, "E00"]), HTTP_COOKIE=COOKIE
    )
    assert (
        client.get(
            reverse("aula-do-curso", args=["profissional", 1, "E01"]),
            HTTP_COOKIE=COOKIE,
        ).status_code
        == 302
    )

    e00 = Progresso.objects.get(aula__numero="E00")
    portas.concluir(e00, laudo=ABERTO)
    assert (
        client.get(
            reverse("aula-do-curso", args=["profissional", 1, "E01"]),
            HTTP_COOKIE=COOKIE,
        ).status_code
        == 200
    )


# ---------------------------------------------- 5. nenhuma view grava
def test_nenhuma_view_nem_gesto_grava_concluida():
    core = Path(__file__).resolve().parents[1] / "apps" / "core"
    fonte = "\n".join(p.read_text(encoding="utf-8") for p in core.glob("*.py"))
    assert not re.search(r"Estado\.CONCLUIDA|[\"']concluida[\"']", fonte)
    assert "concluir(" not in fonte


def test_a_unica_gravacao_de_concluida_esta_em_concluir():
    """No serviço, a palavra `CONCLUIDA` como VALOR gravado aparece uma vez:
    dentro de `concluir`. Um segundo caminho apareceria aqui."""
    fonte = Path(portas.__file__).read_text(encoding="utf-8")
    gravacoes = re.findall(r"[^=!<>]=\s*Progresso\.Estado\.CONCLUIDA", fonte)
    assert len(gravacoes) == 1


# ------------------------------------------------------ 6. a bônus (EB)
def test_a_eb_abre_quando_a_e32_conclui(esqueleto, ana):
    e32 = porta(ana, aula(esqueleto, "E32"))
    portas.concluir(e32, laudo=ABERTO)
    assert estado_de(ana, aula(esqueleto, "EB")) == Progresso.Estado.DISPONIVEL


def test_a_e32_abre_quando_a_e31_conclui_sem_olhar_para_a_eb(esqueleto, ana):
    e31 = porta(ana, aula(esqueleto, "E31"))
    portas.concluir(e31, laudo=ABERTO)
    assert estado_de(ana, aula(esqueleto, "E32")) == Progresso.Estado.DISPONIVEL
    assert estado_de(ana, aula(esqueleto, "EB")) == Progresso.Estado.TRANCADA


def test_a_eb_nao_tranca_ninguem_porque_nada_vem_depois_dela(esqueleto, ana):
    eb = porta(ana, aula(esqueleto, "EB"))
    portas.concluir(eb, laudo=ABERTO)
    assert Progresso.objects.filter(pessoa=ana).count() == 1


# ------------------------------------------ 7. o gesto do curso livre
@pytest.fixture
def livre(db):
    """Um curso de progressão livre com três aulas (a primeira com duas pausas)."""
    curso = Curso.objects.create(
        site_id=SITE,
        slug="livre",
        nome="Curso livre",
        progressao=Curso.Progressao.LIVRE,
    )
    bloco = Bloco.objects.create(curso=curso, ordem=1, letra="A", parte=1)
    for ordem, numero in enumerate(["1", "2", "3"]):
        Aula.objects.create(
            curso=curso, bloco=bloco, ordem=ordem, numero=numero, titulo_exibido=numero
        )
    publicar(curso.aulas.get(numero="1"))
    return curso


@pytest.fixture
def bia(livre):
    return Pessoa.objects.create(id_da_plataforma="p_bia", nome_exibido="Bia")


def registrar_todas(progresso: Progresso) -> None:
    for pausa in progresso.aula.pausas.all():
        RegistroDePausa.objects.create(
            pessoa=progresso.pessoa, pausa=pausa, respostas={"x": "y"}
        )


def test_o_gesto_recusa_o_curso_por_laudo(esqueleto, ana):
    e00 = porta(ana, aula(esqueleto, "E00"))
    with pytest.raises(portas.PortaRecusada, match="laudo da professora"):
        portas.concluir_por_gesto(e00)
    e00.refresh_from_db()
    assert e00.estado == Progresso.Estado.EM_PRODUCAO
    assert estado_de(ana, aula(esqueleto, "E01")) == Progresso.Estado.TRANCADA


def test_o_laudo_recusa_o_curso_livre(livre, bia):
    um = porta(bia, aula(livre, "1"))
    registrar_todas(um)
    with pytest.raises(portas.PortaRecusada, match="não tem entrega de checkpoint"):
        portas.concluir(um, laudo=ABERTO)
    um.refresh_from_db()
    assert um.estado == Progresso.Estado.EM_PRODUCAO
    assert estado_de(bia, aula(livre, "2")) == Progresso.Estado.TRANCADA


def test_o_gesto_recusa_com_pausa_faltando(livre, bia):
    um = porta(bia, aula(livre, "1"))
    RegistroDePausa.objects.create(
        pessoa=bia, pausa=um.aula.pausas.get(ordem=1), respostas={"x": "y"}
    )
    with pytest.raises(portas.PortaRecusada, match="todas as pausas"):
        portas.concluir_por_gesto(um)
    um.refresh_from_db()
    assert um.estado == Progresso.Estado.EM_PRODUCAO
    assert um.concluida_em is None
    assert estado_de(bia, aula(livre, "2")) == Progresso.Estado.TRANCADA
    assert OutboxEvent.objects.filter(event="aula.concluida").count() == 0


def test_o_gesto_recusa_a_porta_trancada(livre, bia):
    dois = porta(bia, aula(livre, "2"), Progresso.Estado.TRANCADA)
    with pytest.raises(portas.PortaRecusada, match="trancada"):
        portas.concluir_por_gesto(dois)
    dois.refresh_from_db()
    assert dois.estado == Progresso.Estado.TRANCADA


def test_o_gesto_conclui_e_abre_so_a_ordem_mais_1(livre, bia):
    um = porta(bia, aula(livre, "1"))
    registrar_todas(um)
    portas.concluir_por_gesto(um)
    um.refresh_from_db()
    assert um.estado == Progresso.Estado.CONCLUIDA
    assert um.concluida_em is not None
    assert estado_de(bia, aula(livre, "2")) == Progresso.Estado.DISPONIVEL
    assert estado_de(bia, aula(livre, "3")) == Progresso.Estado.TRANCADA


def test_o_gesto_e_idempotente_e_emite_uma_vez_so(livre, bia):
    um = porta(bia, aula(livre, "1"))
    registrar_todas(um)
    portas.concluir_por_gesto(um)
    primeira = Progresso.objects.get(pk=um.pk).concluida_em
    portas.concluir_por_gesto(um)
    assert Progresso.objects.get(pk=um.pk).concluida_em == primeira
    assert Progresso.objects.filter(pessoa=bia).count() == 2
    assert OutboxEvent.objects.filter(event="aula.concluida").count() == 1


def test_o_gesto_deixa_a_cerimonia_pendente_quando_a_aula_e_boss(livre, bia):
    um = aula(livre, "1")
    um.e_boss = True
    um.save(update_fields=["e_boss"])
    linha = porta(bia, um)
    registrar_todas(linha)
    portas.concluir_por_gesto(linha)
    linha.refresh_from_db()
    assert linha.cerimonia_pendente is True


@pytest.mark.django_db(transaction=True)
def test_o_gesto_emite_aula_concluida_dentro_da_transacao(livre, bia):
    """Sem a transação do teste por cima, `eventos.emitir` recusa qualquer
    emissão fora de `atomic()`: passar aqui é a prova de que o evento nasce
    na mesma transação da porta ([INV-P6]). O envelope credita o ALUNO."""
    um = porta(bia, aula(livre, "1"))
    registrar_todas(um)
    portas.concluir_por_gesto(um)
    evento = OutboxEvent.objects.get(event="aula.concluida")
    assert evento.payload == {
        "site_id": SITE,
        "curso_id": str(livre.pk),
        "aula_id": str(um.aula.pk),
        "e_boss": False,
    }
    assert evento.envelope_extra == {"ator_id": "p_bia"}


def test_o_gesto_so_recebe_o_progresso():
    parametros = inspect.signature(portas.concluir_por_gesto).parameters
    assert list(parametros) == ["progresso"]
