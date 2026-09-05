"""Teste-guarda dos marcos: o que vira conquista, e o que não vira.

O que estes guardas protegem (degrau 9, `PLANO-PAINEL-DE-GESTAO.md` §6.4):

1. **A conquista sai do fato**, com o dia de São Paulo e a linhagem do evento.
2. **Comprar e ser liberado são conquistas DIFERENTES.** É a distinção que o
   mantenedor cravou em 05/09/2026, e a meta do ciclo conta só a primeira.
3. **A data é a da célula dona**, quando ela manda uma (`virou_aluno_em`).
4. **Um marco por sujeito por tipo**, e um fato mais antigo que chega depois
   puxa a data para trás em vez de deixar a pessoa no mês errado.
5. **O autor de um fato do fórum vem do envelope**, e o da resposta aceita é
   quem ESCREVEU, nunca quem marcou.
6. **Miolo fora do contrato não custa o fato**: guarda o evento, marco nenhum.
7. **Marco assinado não entra nesta tabela.**

A régua deste arquivo é a lista de formas de um número de marco mentir: contar
um fuso errado, contar uma venda que foi liberação, contar duas vezes a mesma
pessoa, contar a pessoa errada, contar no mês errado e contar como medido algo
que alguém declarou à mão.
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.fatos.marcos import derivar
from apps.fatos.models import Evento, Marco
from apps.fatos.recepcao import GUARDADO, JA_TINHA, receber

pytestmark = pytest.mark.django_db

# 01h de UTC do dia 1º: ainda é dia 30 em São Paulo (`armadilhas/099`).
NA_VIRADA = "2026-10-01T01:00:00+00:00"
DEPOIS = "2026-10-05T15:00:00+00:00"


def entregar(assunto: str, dados: dict, quando: str = NA_VIRADA, ator=None) -> str:
    """Entrega um envelope pela porta de verdade e devolve o `event_id`."""
    event_id = str(uuid.uuid4())
    corpo = {
        "event": assunto,
        "version": 1,
        "event_id": event_id,
        "occurred_at": quando,
        "data": {"site_id": "meshcraft", **dados},
    }
    if ator is not None:
        corpo["ator_id"] = ator
    desfecho, _ = receber(json.dumps(corpo))
    assert desfecho == GUARDADO
    return event_id


def matricula(**sobre) -> dict:
    corpo = {"matricula_id": "mat-1", "situacao_nova": "ativa", "origem": "comprou"}
    corpo.update(sobre)
    return corpo


def test_o_cadastro_vira_a_conquista_de_entrar_no_site():
    event_id = entregar("identidade.pessoa-cadastrada", {"pessoa_id": "p-1"})
    marco = Marco.objects.get()
    assert marco.tipo == Marco.Tipo.ENTROU_NO_SITE
    assert marco.sujeito_tipo == Marco.Sujeito.PESSOA
    assert marco.sujeito_id == "p-1"
    assert marco.procedencia == Marco.Procedencia.AUTOMATICO
    assert str(marco.event_id) == event_id, "o marco cita o fato que o produziu"


def test_o_dia_do_marco_e_o_de_sao_paulo_e_nao_o_de_utc():
    entregar("identidade.pessoa-cadastrada", {"pessoa_id": "p-1"})
    assert str(Marco.objects.get().dia) == "2026-09-30", (
        "01h de UTC do dia 1º ainda é o dia 30 aqui, e contar por UTC põe a "
        "pessoa no mês seguinte (`armadilhas/099`)"
    )


def test_pedir_entrada_e_virar_aluno_sao_conquistas_da_matricula():
    entregar("matricula.situacao-alterada", matricula(situacao_nova="aguardando"))
    marco = Marco.objects.get()
    assert marco.tipo == Marco.Tipo.PEDIU_ENTRADA
    assert marco.sujeito_tipo == Marco.Sujeito.MATRICULA, (
        "o contrato manda o id da MATRÍCULA, que não identifica a pessoa: "
        "guardá-lo como pessoa misturaria dois vocabulários na mesma contagem"
    )
    assert marco.sujeito_id == "mat-1"


def test_comprar_e_ser_liberado_sao_marcos_diferentes():
    entregar("matricula.situacao-alterada", matricula(origem="comprou"))
    entregar(
        "matricula.situacao-alterada",
        matricula(matricula_id="mat-2", origem="liberado"),
    )
    assert set(Marco.objects.values_list("sujeito_id", "tipo")) == {
        ("mat-1", Marco.Tipo.VIROU_ALUNO_COMPRANDO),
        ("mat-2", Marco.Tipo.VIROU_ALUNO_LIBERADO),
    }, "a meta do ciclo conta a venda, e não o aluno das turmas anteriores"


def test_a_data_de_virar_aluno_e_a_que_a_celula_dona_mandou():
    entregar(
        "matricula.situacao-alterada",
        matricula(virou_aluno_em="2026-09-15T12:00:00+00:00"),
        quando=DEPOIS,
    )
    assert str(Marco.objects.get().dia) == "2026-09-15", (
        "`virou_aluno_em` é a regra da célula dona; recalcular pelo instante "
        "do evento daria outra data no primeiro caso de borda"
    )


def test_sem_a_data_da_celula_dona_vale_o_instante_do_fato():
    entregar("matricula.situacao-alterada", matricula(virou_aluno_em=None))
    assert str(Marco.objects.get().dia) == "2026-09-30"


@pytest.mark.parametrize(
    "situacao", ["recusada", "suspensa", "encerrada", "reembolsada"]
)
def test_situacao_que_nao_e_conquista_nao_vira_marco(situacao):
    entregar("matricula.situacao-alterada", matricula(situacao_nova=situacao))
    assert Evento.objects.count() == 1, "o fato entra no livro de todo jeito"
    assert Marco.objects.count() == 0, "perder acesso não é conquista"


def test_a_mesma_entrega_duas_vezes_nao_cria_dois_marcos():
    corpo = json.dumps(
        {
            "event": "identidade.pessoa-cadastrada",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": NA_VIRADA,
            "data": {"site_id": "meshcraft", "pessoa_id": "p-1"},
        }
    )
    assert receber(corpo)[0] == GUARDADO
    assert receber(corpo)[0] == JA_TINHA
    assert Marco.objects.count() == 1


def test_dois_fatos_da_mesma_pessoa_dao_um_marco_so():
    entregar("forum.mensagem-criada", {"mensagem_id": "m-1"}, ator="p-1")
    entregar("forum.mensagem-criada", {"mensagem_id": "m-2"}, ator="p-1", quando=DEPOIS)
    assert Marco.objects.count() == 1, "a conquista é escrever no fórum, não cada linha"
    assert str(Marco.objects.get().dia) == "2026-09-30", "vale a primeira vez"


def test_fato_mais_antigo_que_chega_depois_puxa_a_data_para_tras():
    entregar("forum.mensagem-criada", {"mensagem_id": "m-2"}, ator="p-1", quando=DEPOIS)
    antigo = entregar("forum.topico-criado", {"topico_id": "t-1"}, ator="p-1")
    marco = Marco.objects.get()
    assert str(marco.dia) == "2026-09-30", (
        "dois streams não chegam em ordem entre si, e a data mais nova poria "
        "a pessoa na coorte errada"
    )
    assert str(marco.event_id) == antigo, "a linhagem aponta para a data que ficou"


def test_fato_mais_novo_que_chega_depois_nao_mexe_no_marco():
    primeiro = entregar("forum.topico-criado", {"topico_id": "t-1"}, ator="p-1")
    entregar("forum.mensagem-criada", {"mensagem_id": "m-1"}, ator="p-1", quando=DEPOIS)
    marco = Marco.objects.get()
    assert str(marco.dia) == "2026-09-30"
    assert str(marco.event_id) == primeiro


def test_quem_escreveu_no_forum_vem_do_ator_do_envelope():
    entregar("forum.topico-criado", {"topico_id": "t-1", "area_id": "a-1"}, ator="p-9")
    assert Evento.objects.get().ator_id == "p-9", "o livro guarda o autor do envelope"
    marco = Marco.objects.get()
    assert marco.tipo == Marco.Tipo.ESCREVEU_NO_FORUM
    assert marco.sujeito_id == "p-9"


def test_fato_de_forum_sem_ator_nao_vira_marco():
    entregar("forum.topico-criado", {"topico_id": "t-1"})
    assert Evento.objects.count() == 1
    assert Marco.objects.count() == 0, "sem autor não há de quem seja a conquista"


def test_a_resposta_aceita_premia_quem_escreveu_e_nao_quem_marcou():
    entregar(
        "forum.resposta-aceita",
        {"mensagem_id": "m-1", "autor_da_resposta_id": "p-autor"},
        ator="p-marcou",
    )
    marco = Marco.objects.get()
    assert marco.tipo == Marco.Tipo.AJUDOU_ALGUEM
    assert marco.sujeito_id == "p-autor", (
        "o `ator_id` do envelope aqui é de quem marcou, e usá-lo daria a "
        "conquista à pessoa errada"
    )


@pytest.mark.parametrize(
    "assunto,dados",
    [
        ("quiz.completado", {"lead": {"email": "alguem@exemplo.com"}}),
        ("sugestao.criada", {"sugestao_id": "s-1"}),
        ("forum.mensagem-removida", {"mensagem_id": "m-1"}),
    ],
)
def test_assunto_sem_regra_entra_como_fato_e_nao_vira_marco(assunto, dados):
    entregar(assunto, dados, ator="p-1")
    assert Evento.objects.count() == 1
    assert Marco.objects.count() == 0


def test_miolo_fora_do_contrato_guarda_o_fato_e_nao_inventa_marco():
    """O envelope é o que se valida na porta; o miolo pode vir torto."""
    for dados in [
        {},
        {"matricula_id": "mat-1"},
        {"matricula_id": 7, "situacao_nova": "ativa", "origem": "comprou"},
        {"matricula_id": "mat-1", "situacao_nova": "ativa", "origem": "sei-la"},
        {
            "matricula_id": "mat-1",
            "situacao_nova": "ativa",
            "origem": "comprou",
            "virou_aluno_em": "sem-fuso-nenhum",
        },
    ]:
        entregar("matricula.situacao-alterada", dados)
    assert Evento.objects.count() == 5, "nenhum fato foi perdido por causa da leitura"
    assert Marco.objects.filter(sujeito_id="mat-1").count() <= 1
    assert not Marco.objects.filter(dia__isnull=True).exists()


def test_id_maior_que_a_coluna_e_recusado_em_vez_de_cortado():
    entregar("identidade.pessoa-cadastrada", {"pessoa_id": "p" * 121})
    assert Marco.objects.count() == 0, (
        "cortar o id juntaria dois sujeitos diferentes no mesmo marco, e a "
        "contagem encolheria sem ninguém ver"
    )


def test_o_banco_recusa_duas_linhas_da_mesma_conquista():
    """A unicidade é da TABELA, e não da função que grava.

    Sem a trava no banco, um segundo processo derivando o mesmo fato no mesmo
    instante criaria a segunda linha, e a conquista passaria a valer dois na
    contagem.
    """
    campos = {
        "sujeito_tipo": Marco.Sujeito.PESSOA,
        "sujeito_id": "p-1",
        "tipo": Marco.Tipo.ENTROU_NO_SITE,
        "dia": "2026-09-30",
    }
    Marco.objects.create(event_id=uuid.uuid4(), **campos)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Marco.objects.create(event_id=uuid.uuid4(), **campos)
    assert Marco.objects.count() == 1


def test_a_tabela_recusa_marco_assinado():
    with pytest.raises(ValueError, match="marco automático"):
        Marco.objects.create(
            sujeito_tipo=Marco.Sujeito.PESSOA,
            sujeito_id="p-1",
            tipo=Marco.Tipo.ENTROU_NO_SITE,
            dia="2026-09-30",
            event_id=uuid.uuid4(),
            procedencia=Marco.Procedencia.ASSINADO,
        )
    assert Marco.objects.count() == 0


def test_derivar_marcos_alcanca_o_fato_guardado_antes_da_tabela(capsys):
    """A passada sobre o livro é o que salva a história já guardada."""
    entregar("identidade.pessoa-cadastrada", {"pessoa_id": "p-1"})
    Marco.objects.all().delete()

    call_command("derivar_marcos")

    assert Marco.objects.count() == 1
    assert "1 marcos novos" in capsys.readouterr().out


def test_derivar_marcos_avisa_dos_fatos_de_forum_sem_autor(capsys):
    entregar("forum.topico-criado", {"topico_id": "t-1"})
    call_command("derivar_marcos")
    saida = capsys.readouterr().out
    assert (
        "1 fatos de fórum estão guardados sem `ator_id`" in saida
    ), "buraco na contagem se diz na tela, não se deixa em silêncio"


def test_derivar_e_idempotente_sobre_o_livro_inteiro():
    entregar("identidade.pessoa-cadastrada", {"pessoa_id": "p-1"})
    entregar("matricula.situacao-alterada", matricula())
    antes = Marco.objects.count()
    for evento in Evento.objects.all():
        derivar(evento)
        derivar(evento)
    assert Marco.objects.count() == antes == 2
